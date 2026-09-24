from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


FEATURES = [
    "on_hand",
    "reserved",
    "demand_7d",
    "demand_30d",
    "demand_std_30d",
    "forecast_7d",
    "lead_time_days",
    "supplier_reliability",
    "sales_growth",
    "seasonality",
    "lead_time_demand",
    "inventory_gap",
    "demand_velocity",
    "demand_volatility",
    "snapshot_month_sin",
    "snapshot_month_cos",
    "snapshot_progress",
]


def _prepare_demand(demand):
    d = demand.copy()

    date_col = (
        "demand_date"
        if "demand_date" in d.columns
        else "date"
    )

    demand_col = (
        "demand_units"
        if "demand_units" in d.columns
        else "demand"
    )

    required = {
        "product_id",
        date_col,
        demand_col,
    }

    if not required.issubset(d.columns):
        raise ValueError(
            "Demand must contain product_id, date and demand columns."
        )

    d["product_id"] = (
        d["product_id"]
        .astype(str)
    )

    d["demand_date"] = pd.to_datetime(
        d[date_col],
        errors="coerce",
    )

    d["demand_units"] = (
        pd.to_numeric(
            d[demand_col],
            errors="coerce",
        )
        .fillna(0.0)
    )

    return (
        d.dropna(
            subset=[
                "demand_date",
                "product_id",
            ]
        )
        .groupby(
            [
                "product_id",
                "demand_date",
            ],
            as_index=False,
        )["demand_units"]
        .sum()
        .sort_values(
            [
                "product_id",
                "demand_date",
            ]
        )
    )


def _historical_features(
    d,
    date,
):
    historical = d[
        d.demand_date < date
    ]

    columns = [
        "product_id",
        "demand_7d",
        "demand_30d",
        "demand_std_30d",
        "prev_30d",
        "sales_growth",
        "forecast_7d",
        "demand_velocity",
        "demand_volatility",
    ]

    if historical.empty:
        return pd.DataFrame(
            columns=columns
        )

    d7 = historical[
        historical.demand_date
        >= date - pd.Timedelta(days=7)
    ]

    d30 = historical[
        historical.demand_date
        >= date - pd.Timedelta(days=30)
    ]

    prev = historical[
        (
            historical.demand_date
            >= date - pd.Timedelta(days=60)
        )
        & (
            historical.demand_date
            < date - pd.Timedelta(days=30)
        )
    ]

    d7_sum = (
        d7.groupby(
            "product_id"
        )
        .demand_units
        .sum()
    )

    d30_sum = (
        d30.groupby(
            "product_id"
        )
        .demand_units
        .sum()
    )

    d30_std = (
        d30.groupby(
            "product_id"
        )
        .demand_units
        .std()
    )

    prev_sum = (
        prev.groupby(
            "product_id"
        )
        .demand_units
        .sum()
    )

    out = pd.DataFrame(
        {
            "demand_7d": d7_sum,
            "demand_30d": d30_sum,
            "demand_std_30d": d30_std,
            "prev_30d": prev_sum,
        }
    ).fillna(0.0)

    out["sales_growth"] = np.where(
        out["prev_30d"] > 0,
        (
            out["demand_30d"]
            - out["prev_30d"]
        )
        / out["prev_30d"],
        0.0,
    )

    out["sales_growth"] = (
        out["sales_growth"]
        .replace(
            [
                np.inf,
                -np.inf,
            ],
            0.0,
        )
        .clip(
            -10.0,
            10.0,
        )
    )

    out["forecast_7d"] = (
        out["demand_30d"]
        / 30.0
        * 7.0
    )

    out["demand_velocity"] = (
        out["demand_7d"]
        / 7.0
    )

    out["demand_volatility"] = (
        out["demand_std_30d"]
        / np.maximum(
            out["demand_30d"] / 30.0,
            1e-6,
        )
    ).clip(
        0.0,
        100.0,
    )

    return out.reset_index()


def _future_demand(
    d,
    date,
    horizon_days,
):
    future = d[
        (d.demand_date >= date)
        & (
            d.demand_date
            < date
            + pd.Timedelta(
                days=horizon_days
            )
        )
    ]

    if future.empty:
        return pd.Series(
            dtype=float
        )

    return (
        future.groupby(
            "product_id"
        )
        .demand_units
        .sum()
    )


def _label(
    d,
    date,
    inv,
    lead_times,
):
    lead = pd.to_numeric(
        lead_times,
        errors="coerce",
    ).fillna(7.0)

    horizon = max(
        7,
        int(
            np.ceil(
                float(
                    lead.median()
                )
            )
        ),
    )

    future = _future_demand(
        d,
        date,
        horizon,
    )

    product_ids = (
        inv["product_id"]
        .astype(str)
    )

    future_units = (
        product_ids
        .map(future)
        .fillna(0.0)
        .to_numpy(
            dtype=float
        )
    )

    on_hand = (
        pd.to_numeric(
            inv["on_hand"],
            errors="coerce",
        )
        .fillna(0.0)
        .to_numpy(
            dtype=float
        )
    )

    reserved = (
        pd.to_numeric(
            inv["reserved"],
            errors="coerce",
        )
        .fillna(0.0)
        .to_numpy(
            dtype=float
        )
    )

    available = np.maximum(
        on_hand - reserved,
        0.0,
    )

    safety_buffer = np.maximum(
        future_units * 0.10,
        1.0,
    )

    required_inventory = (
        future_units
        + safety_buffer
    )

    return (
        (
            future_units > 0
        )
        & (
            available
            < required_inventory
        )
    ).astype(
        np.int8
    )


def _calendar_features(
    date,
    start_date,
    end_date,
):
    month = date.month

    month_angle = (
        2.0
        * np.pi
        * (month - 1)
        / 12.0
    )

    total_days = max(
        (
            pd.Timestamp(end_date)
            - pd.Timestamp(start_date)
        ).days,
        1,
    )

    elapsed_days = (
        date
        - pd.Timestamp(start_date)
    ).days

    progress = np.clip(
        elapsed_days
        / total_days,
        0.0,
        1.0,
    )

    return {
        "snapshot_month_sin": float(
            np.sin(month_angle)
        ),
        "snapshot_month_cos": float(
            np.cos(month_angle)
        ),
        "snapshot_progress": float(
            progress
        ),
    }


def build_stockout_dataset(
    inventory,
    demand,
    suppliers,
    supplier_products,
):
    inv = inventory.copy()

    required_inventory_columns = {
        "snapshot_date",
        "warehouse_id",
        "product_id",
        "on_hand",
        "reserved",
    }

    if not required_inventory_columns.issubset(
        inv.columns
    ):
        raise ValueError(
            "Inventory is missing required columns."
        )

    inv["snapshot_date"] = pd.to_datetime(
        inv["snapshot_date"],
        errors="coerce",
    )

    inv["warehouse_id"] = (
        inv["warehouse_id"]
        .astype(str)
    )

    inv["product_id"] = (
        inv["product_id"]
        .astype(str)
    )

    inv["on_hand"] = (
        pd.to_numeric(
            inv["on_hand"],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(lower=0.0)
    )

    inv["reserved"] = (
        pd.to_numeric(
            inv["reserved"],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(lower=0.0)
    )

    inv["reserved"] = np.minimum(
        inv["reserved"],
        inv["on_hand"],
    )

    d = _prepare_demand(
        demand
    )

    s = suppliers.copy()

    s["supplier_id"] = (
        s["supplier_id"]
        .astype(str)
    )

    s["lead_time_days"] = (
        pd.to_numeric(
            s["lead_time_days"],
            errors="coerce",
        )
    )

    s["reliability"] = (
        pd.to_numeric(
            s["reliability"],
            errors="coerce",
        )
    )

    links = supplier_products.copy()

    links["supplier_id"] = (
        links["supplier_id"]
        .astype(str)
    )

    links["product_id"] = (
        links["product_id"]
        .astype(str)
    )

    links = links.merge(
        s[
            [
                "supplier_id",
                "lead_time_days",
                "reliability",
            ]
        ],
        on="supplier_id",
        how="left",
    )

    sp = (
        links.groupby(
            "product_id",
            as_index=False,
        )
        .agg(
            lead_time_days=(
                "lead_time_days",
                "median",
            ),
            supplier_reliability=(
                "reliability",
                "max",
            ),
        )
    )

    default_lead = (
        float(
            s["lead_time_days"]
            .median()
        )
        if not s.empty
        else 7.0
    )

    default_reliability = (
        float(
            s["reliability"]
            .median()
        )
        if not s.empty
        else 0.85
    )

    start_date = (
        inv["snapshot_date"]
        .min()
    )

    end_date = (
        inv["snapshot_date"]
        .max()
    )

    frames = []

    dates = sorted(
        inv["snapshot_date"]
        .dropna()
        .unique()
    )

    for date_value in dates:
        date = pd.Timestamp(
            date_value
        )

        x = inv[
            inv["snapshot_date"]
            == date
        ].copy()

        historical = (
            _historical_features(
                d,
                date,
            )
        )

        x = x.merge(
            historical,
            on="product_id",
            how="left",
        )

        x = x.merge(
            sp,
            on="product_id",
            how="left",
        )

        defaults = {
            "demand_7d": 0.0,
            "demand_30d": 0.0,
            "demand_std_30d": 0.0,
            "prev_30d": 0.0,
            "sales_growth": 0.0,
            "forecast_7d": 0.0,
            "demand_velocity": 0.0,
            "demand_volatility": 0.0,
            "lead_time_days": default_lead,
            "supplier_reliability": (
                default_reliability
            ),
        }

        for column, value in defaults.items():
            x[column] = (
                pd.to_numeric(
                    x[column],
                    errors="coerce",
                )
                .fillna(value)
            )

        x["sales_growth"] = (
            x["sales_growth"]
            .replace(
                [
                    np.inf,
                    -np.inf,
                ],
                0.0,
            )
            .clip(
                -10.0,
                10.0,
            )
        )

        calendar = _calendar_features(
            date,
            start_date,
            end_date,
        )

        for column, value in calendar.items():
            x[column] = value

        x["seasonality"] = (
            x["snapshot_month_sin"]
        )

        x["available_inventory"] = (
            x["on_hand"]
            - x["reserved"]
        ).clip(
            lower=0.0
        )

        x["lead_time_demand"] = (
            x["demand_30d"]
            / 30.0
            * x["lead_time_days"]
        )

        safety_stock = np.maximum(
            x["demand_std_30d"]
            * np.sqrt(
                np.maximum(
                    x["lead_time_days"],
                    1.0,
                )
            ),
            0.0,
        )

        x["inventory_gap"] = (
            x["available_inventory"]
            - x["lead_time_demand"]
            - safety_stock
        )

        x["stockout"] = _label(
            d,
            date,
            x,
            x["lead_time_days"],
        )

        daily_demand = np.maximum(
            x["demand_30d"]
            / 30.0,
            1e-6,
        )

        x["days_of_cover"] = np.clip(
            x["available_inventory"]
            / daily_demand,
            0.0,
            3650.0,
        )

        frames.append(
            x[
                [
                    "snapshot_date",
                    "warehouse_id",
                    "product_id",
                    *FEATURES,
                    "available_inventory",
                    "days_of_cover",
                    "stockout",
                ]
            ]
        )

    if not frames:
        raise ValueError(
            "No valid stockout training rows were generated."
        )

    result = (
        pd.concat(
            frames,
            ignore_index=True,
        )
        .sort_values(
            [
                "snapshot_date",
                "warehouse_id",
                "product_id",
            ]
        )
        .reset_index(drop=True)
    )

    return result


def risk_level(
    probability,
):
    if probability >= 0.85:
        return "Critical"

    if probability >= 0.60:
        return "High"

    if probability >= 0.30:
        return "Medium"

    return "Low"


def _positive_probability(
    model,
    features,
):
    probabilities = model.predict_proba(
        features
    )

    classes = list(
        getattr(
            model,
            "classes_",
            [],
        )
    )

    if 1 in classes:
        return probabilities[
            :,
            classes.index(1),
        ]

    return np.zeros(
        len(features),
        dtype=float,
    )


class StockoutModel:
    def __init__(
        self,
        model_dir,
    ):
        self.model_dir = Path(
            model_dir
        )

        self.model_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def train(
        self,
        df,
        max_train_rows=120_000,
    ):
        data = (
            df.dropna(
                subset=FEATURES
                + ["stockout"]
            )
            .sort_values(
                "snapshot_date"
            )
            .reset_index(drop=True)
        )

        data["stockout"] = (
            pd.to_numeric(
                data["stockout"],
                errors="coerce",
            )
            .fillna(0)
            .astype(int)
        )

        dates = sorted(
            data["snapshot_date"]
            .unique()
        )

        if len(dates) < 3:
            raise ValueError(
                "At least three temporal dates are required."
            )

        if data["stockout"].nunique() < 2:
            raise ValueError(
                "Stockout target contains only one class."
            )

        split = max(
            1,
            int(
                len(dates) * 0.75
            ),
        )

        split = min(
            split,
            len(dates) - 1,
        )

        train_dates = dates[
            :split
        ]

        test_dates = dates[
            split:
        ]

        train = data[
            data["snapshot_date"]
            .isin(train_dates)
        ].copy()

        test = data[
            data["snapshot_date"]
            .isin(test_dates)
        ].copy()

        while (
            train["stockout"].nunique()
            < 2
            and len(train_dates)
            < len(dates) - 1
        ):
            train_dates.append(
                dates[
                    len(train_dates)
                ]
            )

            test_dates = dates[
                len(train_dates):
            ]

            train = data[
                data["snapshot_date"]
                .isin(train_dates)
            ].copy()

            test = data[
                data["snapshot_date"]
                .isin(test_dates)
            ].copy()

        if train["stockout"].nunique() < 2:
            raise ValueError(
                "Unable to create a temporal training split containing both classes."
            )

        if test.empty:
            raise ValueError(
                "Temporal validation set is empty."
            )

        if test["stockout"].nunique() < 2:
            raise ValueError(
                "Temporal validation set must contain both stockout classes."
            )

        if len(train) > max_train_rows:
            positives = train[
                train["stockout"] == 1
            ]

            negatives = train[
                train["stockout"] == 0
            ]

            positive_limit = min(
                len(positives),
                max_train_rows // 2,
            )

            negative_limit = (
                max_train_rows
                - positive_limit
            )

            positive_sample = (
                positives.sample(
                    n=positive_limit,
                    random_state=42,
                )
                if positive_limit > 0
                else positives
            )

            negative_sample = (
                negatives.sample(
                    n=min(
                        negative_limit,
                        len(negatives),
                    ),
                    random_state=42,
                )
                if len(negatives) > 0
                else negatives
            )

            train = pd.concat(
                [
                    positive_sample,
                    negative_sample,
                ],
                ignore_index=True,
            )

            train = (
                train.sample(
                    frac=1.0,
                    random_state=42,
                )
                .reset_index(drop=True)
            )

        model = RandomForestClassifier(
            n_estimators=160,
            max_depth=10,
            min_samples_leaf=4,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=2,
        )

        model.fit(
            train[FEATURES],
            train["stockout"],
        )

        probability = (
            _positive_probability(
                model,
                test[FEATURES],
            )
        )

        prediction = (
            probability >= 0.50
        ).astype(int)

        y = test[
            "stockout"
        ].astype(int)

        scores = {
            "precision": float(
                precision_score(
                    y,
                    prediction,
                    zero_division=0,
                )
            ),
            "recall": float(
                recall_score(
                    y,
                    prediction,
                    zero_division=0,
                )
            ),
            "f1": float(
                f1_score(
                    y,
                    prediction,
                    zero_division=0,
                )
            ),
            "roc_auc": float(
                roc_auc_score(
                    y,
                    probability,
                )
            ),
            "pr_auc": float(
                average_precision_score(
                    y,
                    probability,
                )
            ),
        }

        artifact = {
            "model": model,
            "features": FEATURES,
            "metrics": scores,
            "model_name": (
                "RandomForestClassifier"
            ),
            "training_rows": len(train),
            "validation_rows": len(test),
            "training_rows_available": len(
                data[
                    data["snapshot_date"]
                    .isin(train_dates)
                ]
            ),
            "training_start": str(
                min(train_dates)
            ),
            "training_end": str(
                max(train_dates)
            ),
            "validation_start": str(
                min(test_dates)
            ),
            "validation_end": str(
                max(test_dates)
            ),
            "target": (
                "synthetic_forward_stockout"
            ),
            "target_definition": (
                "Stockout is positive when future "
                "observed product demand during the "
                "supplier lead-time protection window "
                "plus a 10 percent demand buffer exceeds "
                "available inventory at the snapshot."
            ),
            "data_note": (
                "Olist has no warehouse stockout ground "
                "truth. The target is synthetically derived "
                "from future observed demand."
            ),
            "leakage_control": (
                "Future demand is used only for target "
                "construction. Current available inventory "
                "is represented through operational features "
                "without using available_inventory directly."
            ),
        }

        joblib.dump(
            artifact,
            self.model_dir
            / "stockout_model.joblib",
        )

        return scores

    def load(self):
        path = (
            self.model_dir
            / "stockout_model.joblib"
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Stockout model not found: {path}"
            )

        return joblib.load(
            path
        )

    def predict(
        self,
        df,
    ):
        artifact = self.load()

        model = artifact["model"]

        features = artifact[
            "features"
        ]

        missing = [
            column
            for column in features
            if column not in df.columns
        ]

        if missing:
            raise ValueError(
                f"Missing stockout features: {missing}"
            )

        probability = (
            _positive_probability(
                model,
                df[features],
            )
        )

        out = df[
            [
                "warehouse_id",
                "product_id",
            ]
        ].copy()

        out[
            "stockout_probability"
        ] = probability

        out["risk_level"] = [
            risk_level(
                float(
                    probability_value
                )
            )
            for probability_value in probability
        ]

        daily_demand = np.maximum(
            pd.to_numeric(
                df["demand_30d"],
                errors="coerce",
            )
            .fillna(0.0)
            .to_numpy()
            / 30.0,
            1e-6,
        )

        available = np.maximum(
            pd.to_numeric(
                df[
                    "available_inventory"
                ],
                errors="coerce",
            )
            .fillna(0.0)
            .to_numpy(),
            0.0,
        )

        days_of_cover = np.clip(
            np.nan_to_num(
                available
                / daily_demand,
                nan=3650.0,
                posinf=3650.0,
                neginf=0.0,
            ),
            0.0,
            3650.0,
        )

        out[
            "days_of_cover"
        ] = days_of_cover

        out[
            "expected_stockout_date"
        ] = (
            pd.to_datetime(
                df["snapshot_date"],
                errors="coerce",
            )
            + pd.to_timedelta(
                days_of_cover,
                unit="D",
            )
        )

        return out