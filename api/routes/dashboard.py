from __future__ import annotations

import gc
from pathlib import Path
import pandas as pd
from fastapi import APIRouter

from api.services.data import DataRepository

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
repo = DataRepository()

_UNSET = object()
_cache = {
    "stockout_risks": _UNSET,
    "inventory_value": _UNSET,
    "daily_sales": _UNSET,
    "delivery_risks": _UNSET,
    "supplier_risks": _UNSET,
}


def _processed_path(name: str) -> Path:
    return repo.root / name


def _read_csv(name: str, usecols: list[str] | None = None, dtype: dict | None = None) -> pd.DataFrame:
    path = _processed_path(name)
    if not path.exists():
        return pd.DataFrame()
    if usecols:
        kwargs: dict = {"usecols": usecols}
        if dtype:
            kwargs["dtype"] = {k: v for k, v in dtype.items() if k in usecols}
        try:
            return pd.read_csv(path, **kwargs)
        except ValueError:
            return pd.read_csv(path)
    return pd.read_csv(path)


def _forecast_metrics() -> dict:
    import joblib

    path = Path("ml/models/demand_forecast.joblib")

    if not path.exists():
        return {}

    try:
        artifact = joblib.load(path)
    except Exception:
        return {}

    if not isinstance(artifact, dict):
        return {}

    evaluation = artifact.get("evaluation", {})
    selected_model = artifact.get("selected_model")

    if not isinstance(evaluation, dict) or not selected_model:
        return {}

    metrics = evaluation.get(selected_model, {})

    if not isinstance(metrics, dict):
        return {}

    wape = metrics.get("WAPE")

    if wape is None:
        return {
            "selected_model": selected_model,
            "metrics": metrics,
        }

    return {
        "selected_model": selected_model,
        "wape": float(wape),
        "smape": (
            float(metrics["sMAPE"])
            if metrics.get("sMAPE") is not None
            else None
        ),
        "mae": (
            float(metrics["MAE"])
            if metrics.get("MAE") is not None
            else None
        ),
        "rmse": (
            float(metrics["RMSE"])
            if metrics.get("RMSE") is not None
            else None
        ),
        "accuracy": float(max(0.0, 1.0 - float(wape))),
    }


def _inventory_value():
    if _cache["inventory_value"] is not _UNSET:
        return _cache["inventory_value"]

    _cache["inventory_value"] = _compute_inventory_value()
    return _cache["inventory_value"]


# inventory_snapshots.csv holds 3.16 M rows over 8 snapshot dates.  Materialising
# the whole frame just to read one date costs 242 MiB (the snapshot_date strings
# alone are ~190 MiB) and peaked the process at 420 MiB - the single largest
# allocation in the Dashboard warm-up.  Streaming it keeps only the newest
# snapshot (395 k rows) and produces byte-identical numbers.
_INVENTORY_CHUNKS = 50_000


def _compute_inventory_value():
    path = _processed_path("inventory_snapshots.csv")
    if not path.exists():
        return None

    # Pass 1: find the latest snapshot date
    latest_snapshot = None
    try:
        chunks = pd.read_csv(
            path,
            usecols=["snapshot_date"],
            chunksize=_INVENTORY_CHUNKS,
        )
        for chunk in chunks:
            chunk_max = chunk["snapshot_date"].max()
            if pd.isna(chunk_max):
                del chunk
                continue
            if latest_snapshot is None or chunk_max > latest_snapshot:
                latest_snapshot = chunk_max
            del chunk
    except ValueError:
        return None

    if latest_snapshot is None:
        return None

    # Load unit costs lookup
    purchase_orders = _read_csv("purchase_orders.csv", usecols=["product_id", "unit_cost"])
    if purchase_orders.empty:
        del purchase_orders
        gc.collect()
        return None

    costs = purchase_orders.dropna(subset=["product_id", "unit_cost"]).groupby("product_id")["unit_cost"].mean()
    del purchase_orders
    gc.collect()

    # Pass 2: stream and accumulate sum(on_hand * unit_cost) for latest snapshot
    total_value = 0.0
    matched_rows = 0
    costed_rows = 0
    try:
        chunks = pd.read_csv(
            path,
            usecols=["snapshot_date", "product_id", "on_hand"],
            dtype={"product_id": "category"},
            chunksize=_INVENTORY_CHUNKS,
        )
        for chunk in chunks:
            mask = chunk["snapshot_date"].eq(latest_snapshot)
            if not mask.any():
                del chunk
                continue
            matched = chunk.loc[mask]
            matched_rows += len(matched)
            unit_costs = matched["product_id"].map(costs).astype(float)
            valid = unit_costs.notna()
            costed_rows += int(valid.sum())
            total_value += float((matched.loc[valid, "on_hand"] * unit_costs[valid]).sum())
            del chunk, matched, unit_costs, valid
    except ValueError:
        return None

    if matched_rows == 0:
        del costs
        gc.collect()
        return None

    coverage = costed_rows / matched_rows
    if coverage >= 0.95:
        del costs
        gc.collect()
        return total_value

    # purchase_orders.csv only prices 497 of the 32 951 catalogued products
    # (1.5 % of snapshot rows), so an exact valuation is impossible.  Fall back
    # to the mean PO unit cost for the unpriced rows instead of blanking the KPI.
    avg_unit_cost = float(costs.mean()) if len(costs) else 0.0
    unpriced_rows = matched_rows - costed_rows
    result = total_value + unpriced_rows * avg_unit_cost
    del costs
    gc.collect()
    return result


def _stockout_risks() -> dict:
    if _cache["stockout_risks"] is not _UNSET:
        return _cache["stockout_risks"]
    result = repo.stockout_risk_counts()
    _cache["stockout_risks"] = result
    return result


def _delivery_risks() -> dict:
    if _cache["delivery_risks"] is not _UNSET:
        return _cache["delivery_risks"]

    delivery = _read_csv("delivery_risk_predictions.csv", usecols=["order_id", "risk_level"])

    if delivery.empty or "risk_level" not in delivery.columns:
        result = {"count": 0, "high": 0, "critical": 0}
        _cache["delivery_risks"] = result
        return result

    high = delivery["risk_level"].eq("High")
    critical = delivery["risk_level"].eq("Critical")

    if "order_id" in delivery.columns:
        high_orders = delivery.loc[high, "order_id"].dropna().astype(str).drop_duplicates()
        critical_orders = delivery.loc[critical, "order_id"].dropna().astype(str).drop_duplicates()
        risky_orders = delivery.loc[high | critical, "order_id"].dropna().astype(str).drop_duplicates()
        result = {"count": int(len(risky_orders)), "high": int(len(high_orders)), "critical": int(len(critical_orders))}
        _cache["delivery_risks"] = result
        del delivery, high, critical, high_orders, critical_orders, risky_orders
        gc.collect()
        return result

    result = {"count": int((high | critical).sum()), "high": int(high.sum()), "critical": int(critical.sum())}
    _cache["delivery_risks"] = result
    del delivery, high, critical
    gc.collect()
    return result


def _supplier_risks() -> dict:
    if _cache["supplier_risks"] is not _UNSET:
        return _cache["supplier_risks"]

    suppliers = _read_csv("supplier_intelligence.csv", usecols=["risk_level", "supplier_id"])

    if suppliers.empty or "risk_level" not in suppliers.columns:
        result = {"count": 0, "high": 0, "critical": 0}
        _cache["supplier_risks"] = result
        return result

    high = suppliers["risk_level"].eq("High")
    critical = suppliers["risk_level"].eq("Critical")

    if "supplier_id" in suppliers.columns:
        risky = suppliers.loc[high | critical, "supplier_id"].dropna().astype(str).drop_duplicates()
        result = {"count": int(len(risky)), "high": int(high.sum()), "critical": int(critical.sum())}
        _cache["supplier_risks"] = result
        del suppliers, high, critical, risky
        gc.collect()
        return result

    result = {"count": int((high | critical).sum()), "high": int(high.sum()), "critical": int(critical.sum())}
    _cache["supplier_risks"] = result
    del suppliers, high, critical
    gc.collect()
    return result


def _daily_sales() -> dict:
    if _cache["daily_sales"] is not _UNSET:
        return _cache["daily_sales"]
    sales = _read_csv("daily_sales.csv", usecols=["revenue", "orders"])
    result = {
        "revenue": float(sales["revenue"].sum()) if not sales.empty and "revenue" in sales.columns else None,
        "orders": int(sales["orders"].sum()) if not sales.empty and "orders" in sales.columns else None,
    }
    del sales
    gc.collect()
    _cache["daily_sales"] = result
    return result


def _warm_caches() -> None:
    for fn in (
        _stockout_risks,
        _delivery_risks,
        _supplier_risks,
        _inventory_value,
        _daily_sales,
    ):
        fn()
        gc.collect()


@router.get("/summary")
def summary():
    if any(v is _UNSET for v in _cache.values()):
        _warm_caches()

    sales = _daily_sales()
    stockout = _stockout_risks()
    delivery = _delivery_risks()
    suppliers = _supplier_risks()
    forecast = _forecast_metrics()

    optimization = repo.json("phase10_summary.json")
    optimization_savings = optimization.get("estimated_savings")
    if optimization_savings is not None:
        optimization_savings = float(optimization_savings)

    return {
        "revenue": sales["revenue"],
        "orders": sales["orders"],
        "inventory_value": _inventory_value(),
        "stockout_risks": stockout["count"],
        "stockout_high": stockout["high"],
        "stockout_critical": stockout["critical"],
        "delayed_shipments": delivery["count"],
        "delayed_shipments_high": delivery["high"],
        "delayed_shipments_critical": delivery["critical"],
        "forecast_accuracy": forecast.get("accuracy"),
        "forecast_wape": forecast.get("wape"),
        "forecast_smape": forecast.get("smape"),
        "forecast_mae": forecast.get("mae"),
        "forecast_rmse": forecast.get("rmse"),
        "forecast_model": forecast.get("selected_model"),
        "supplier_risks": suppliers["count"],
        "supplier_risks_high": suppliers["high"],
        "supplier_risks_critical": suppliers["critical"],
        "optimization_savings": optimization_savings,
    }