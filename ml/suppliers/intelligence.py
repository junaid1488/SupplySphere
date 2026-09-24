from __future__ import annotations

import numpy as np
import pandas as pd


def _numeric(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def _normalize_rate(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")

    if values.dropna().empty:
        return pd.Series(0.5, index=series.index, dtype=float)

    if float(values.dropna().max()) > 1.0:
        values = values / 100.0

    return values.fillna(0.5).clip(0.0, 1.0)


def _minmax_score(
    series: pd.Series,
    higher_is_better: bool = True,
    neutral: float = 0.5,
) -> pd.Series:
    values = _numeric(series)

    minimum = float(values.min())
    maximum = float(values.max())

    if not np.isfinite(minimum) or not np.isfinite(maximum):
        return pd.Series(neutral, index=series.index, dtype=float)

    if np.isclose(minimum, maximum):
        return pd.Series(neutral, index=series.index, dtype=float)

    score = (values - minimum) / (maximum - minimum)

    if not higher_is_better:
        score = 1.0 - score

    return score.clip(0.0, 1.0)


def _risk_level(score: pd.Series) -> pd.Series:
    return pd.cut(
        score,
        bins=[-np.inf, 25.0, 50.0, 75.0, np.inf],
        labels=["Low", "Medium", "High", "Critical"],
        right=False,
    ).astype(str)


def _risk_drivers(row: pd.Series) -> str:
    drivers = {
        "on-time delivery": 1.0 - float(row["on_time_score"]),
        "reliability": 1.0 - float(row["reliability_score"]),
        "lead-time performance": 1.0 - float(row["lead_time_score"]),
        "lead-time variability": 1.0
        - float(row["lead_time_variability_score"]),
        "quality": 1.0 - float(row["quality_score"]),
        "cost": 1.0 - float(row["cost_score"]),
    }

    ranked = sorted(
        drivers.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    selected = [
        name
        for name, severity in ranked
        if severity >= 0.30
    ][:3]

    if not selected:
        selected = [ranked[0][0]]

    return ", ".join(selected)


def build_supplier_intelligence(
    suppliers: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    shipment_events: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Build supplier intelligence from supported source data.

    Supported sources:
    - suppliers:
        reliability
        lead_time_days
        lead_time_std_days
        capacity_units
        unit_cost
        moq
    - purchase_orders:
        quantity
        unit_cost
        supplier_id
    - shipment_events:
        accepted as an optional argument for pipeline compatibility.

    The current shipment_events source contains only event_id,
    order_id and event_type, so it is intentionally not used to
    calculate supplier-level delivery metrics.
    """

    suppliers_df = suppliers.copy()
    po_df = purchase_orders.copy()

    required_supplier_columns = {
        "supplier_id",
        "reliability",
        "lead_time_days",
        "lead_time_std_days",
        "capacity_units",
        "unit_cost",
        "moq",
    }

    missing_supplier = (
        required_supplier_columns
        - set(suppliers_df.columns)
    )

    if missing_supplier:
        raise ValueError(
            "suppliers missing required columns: "
            + ", ".join(sorted(missing_supplier))
        )

    if "supplier_id" not in po_df.columns:
        raise ValueError(
            "purchase_orders must contain supplier_id"
        )

    suppliers_df["supplier_id"] = (
        suppliers_df["supplier_id"].astype(str)
    )

    po_df["supplier_id"] = (
        po_df["supplier_id"].astype(str)
    )

    if "quantity" in po_df.columns:
        po_df["quantity"] = _numeric(
            po_df["quantity"]
        )
    else:
        po_df["quantity"] = 1.0

    if "unit_cost" in po_df.columns:
        po_df["unit_cost"] = _numeric(
            po_df["unit_cost"]
        )
    else:
        po_df["unit_cost"] = 0.0

    po_df["procurement_value"] = (
        po_df["quantity"]
        * po_df["unit_cost"]
    )

    if "po_id" in po_df.columns:
        order_frequency = (
            po_df.groupby("supplier_id")["po_id"]
            .nunique()
            .rename("order_frequency")
        )
    else:
        order_frequency = (
            po_df.groupby("supplier_id")
            .size()
            .rename("order_frequency")
        )

    po_metrics = pd.DataFrame(
        {
            "order_frequency": order_frequency,
            "procurement_cost": (
                po_df.groupby("supplier_id")[
                    "procurement_value"
                ].sum()
            ),
            "units_ordered": (
                po_df.groupby("supplier_id")[
                    "quantity"
                ].sum()
            ),
        }
    ).reset_index()

    out = suppliers_df.merge(
        po_metrics,
        on="supplier_id",
        how="left",
    )

    out["order_frequency"] = _numeric(
        out["order_frequency"]
    )

    out["procurement_cost"] = _numeric(
        out["procurement_cost"]
    )

    out["units_ordered"] = _numeric(
        out["units_ordered"]
    )

    out["reliability"] = _normalize_rate(
        out["reliability"]
    )

    out["lead_time_days"] = _numeric(
        out["lead_time_days"]
    ).clip(lower=0.0)

    out["lead_time_std_days"] = _numeric(
        out["lead_time_std_days"]
    ).clip(lower=0.0)

    out["capacity_units"] = _numeric(
        out["capacity_units"]
    ).clip(lower=0.0)

    out["unit_cost"] = _numeric(
        out["unit_cost"]
    ).clip(lower=0.0)

    out["moq"] = _numeric(
        out["moq"]
    ).clip(lower=0.0)

    out["on_time_delivery_rate"] = (
        out["reliability"]
    )

    out["defect_rate"] = (
        1.0 - out["reliability"]
    ).clip(0.0, 1.0)

    out["lead_time_score"] = _minmax_score(
        out["lead_time_days"],
        higher_is_better=False,
    )

    out["lead_time_variability_score"] = _minmax_score(
        out["lead_time_std_days"],
        higher_is_better=False,
    )

    out["reliability_score"] = (
        out["reliability"]
    ).clip(0.0, 1.0)

    out["on_time_score"] = (
        out["on_time_delivery_rate"]
    ).clip(0.0, 1.0)

    out["quality_score"] = (
        1.0 - out["defect_rate"]
    ).clip(0.0, 1.0)

    out["cost_score"] = _minmax_score(
        out["unit_cost"],
        higher_is_better=False,
    )

    out["supplier_score"] = (
        100.0
        * (
            0.30 * out["on_time_score"]
            + 0.20 * out["reliability_score"]
            + 0.15 * out["lead_time_score"]
            + 0.10 * out["lead_time_variability_score"]
            + 0.15 * out["quality_score"]
            + 0.10 * out["cost_score"]
        )
    ).clip(0.0, 100.0)

    out["risk_score"] = (
        100.0 - out["supplier_score"]
    ).clip(0.0, 100.0)

    out["risk_level"] = _risk_level(
        out["risk_score"]
    )

    out["risk_drivers"] = out.apply(
        _risk_drivers,
        axis=1,
    )

    out = out.sort_values(
        by=["supplier_score", "supplier_id"],
        ascending=[False, True],
    ).reset_index(drop=True)

    out["supplier_rank"] = (
        np.arange(len(out)) + 1
    )

    out["supplier_rank_percentile"] = (
        1.0
        - (
            (out["supplier_rank"] - 1)
            / max(len(out) - 1, 1)
        )
    ).clip(0.0, 1.0)

    output_columns = [
        "supplier_id",
        "supplier_name",
        "lead_time_days",
        "lead_time_std_days",
        "reliability",
        "capacity_units",
        "unit_cost",
        "moq",
        "order_frequency",
        "procurement_cost",
        "units_ordered",
        "on_time_delivery_rate",
        "defect_rate",
        "lead_time_score",
        "lead_time_variability_score",
        "cost_score",
        "supplier_score",
        "risk_score",
        "risk_level",
        "risk_drivers",
        "supplier_rank",
        "supplier_rank_percentile",
    ]

    for column in output_columns:
        if column not in out.columns:
            raise ValueError(
                f"Required output column missing: {column}"
            )

    result = out[output_columns].copy()

    numeric_columns = [
        "lead_time_days",
        "lead_time_std_days",
        "reliability",
        "capacity_units",
        "unit_cost",
        "moq",
        "order_frequency",
        "procurement_cost",
        "units_ordered",
        "on_time_delivery_rate",
        "defect_rate",
        "lead_time_score",
        "lead_time_variability_score",
        "cost_score",
        "supplier_score",
        "risk_score",
        "supplier_rank",
        "supplier_rank_percentile",
    ]

    result[numeric_columns] = (
        result[numeric_columns]
        .replace([np.inf, -np.inf], np.nan)
    )

    if result[numeric_columns].isna().any().any():
        raise ValueError(
            "Supplier intelligence produced missing numeric values"
        )

    if result["supplier_id"].duplicated().any():
        raise ValueError(
            "Duplicate supplier_id detected"
        )

    if not result["supplier_score"].between(
        0.0,
        100.0,
    ).all():
        raise ValueError(
            "supplier_score outside 0-100 range"
        )

    if not result["risk_score"].between(
        0.0,
        100.0,
    ).all():
        raise ValueError(
            "risk_score outside 0-100 range"
        )

    if not result["risk_level"].isin(
        ["Low", "Medium", "High", "Critical"]
    ).all():
        raise ValueError(
            "Invalid supplier risk level"
        )

    return result