from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import joblib
import pandas as pd
from fastapi import APIRouter

from api.services.data import DataRepository

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
repo = DataRepository()

# Module-level cache for expensive computations
# Processed data is static during server lifetime
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


def _read_csv(name: str, usecols: list[str] | None = None) -> pd.DataFrame:
    path = _processed_path(name)
    if not path.exists():
        return pd.DataFrame()
    if usecols:
        try:
            return pd.read_csv(path, usecols=usecols)
        except ValueError:
            return pd.read_csv(path)
    return pd.read_csv(path)


def _forecast_metrics() -> dict:
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

    inventory = _read_csv(
        "inventory_snapshots.csv",
        usecols=["snapshot_date", "product_id", "on_hand"],
    )
    purchase_orders = _read_csv(
        "purchase_orders.csv",
        usecols=["product_id", "unit_cost"],
    )

    if inventory.empty or purchase_orders.empty:
        _cache["inventory_value"] = None
        return None

    required_inventory = {
        "snapshot_date",
        "product_id",
        "on_hand",
    }

    required_cost = {
        "product_id",
        "unit_cost",
    }

    if not required_inventory.issubset(inventory.columns):
        _cache["inventory_value"] = None
        return None

    if not required_cost.issubset(purchase_orders.columns):
        _cache["inventory_value"] = None
        return None

    latest_snapshot = inventory["snapshot_date"].max()

    latest = inventory[
        inventory["snapshot_date"].eq(latest_snapshot)
    ].copy()

    if latest.empty:
        _cache["inventory_value"] = None
        return None

    costs = (
        purchase_orders
        .dropna(subset=["product_id", "unit_cost"])
        .groupby("product_id")["unit_cost"]
        .mean()
    )

    latest["unit_cost"] = latest["product_id"].map(costs)

    coverage = float(latest["unit_cost"].notna().mean())

    if coverage < 0.95:
        _cache["inventory_value"] = None
        return None

    result = float(
        (latest["on_hand"] * latest["unit_cost"]).sum()
    )
    _cache["inventory_value"] = result
    return result


def _stockout_risks() -> dict:
    if _cache["stockout_risks"] is not _UNSET:
        return _cache["stockout_risks"]

    stockout = _read_csv(
        "stockout_predictions.csv",
        usecols=["warehouse_id", "product_id", "risk_level"],
    )

    if stockout.empty or "risk_level" not in stockout.columns:
        result = {
            "count": 0,
            "high": 0,
            "critical": 0,
        }
        _cache["stockout_risks"] = result
        return result

    high = stockout["risk_level"].eq("High")
    critical = stockout["risk_level"].eq("Critical")

    if {"warehouse_id", "product_id"}.issubset(stockout.columns):
        operational = stockout.loc[
            high | critical,
            ["warehouse_id", "product_id"],
        ].drop_duplicates()

        high_pairs = stockout.loc[
            high,
            ["warehouse_id", "product_id"],
        ].drop_duplicates()

        critical_pairs = stockout.loc[
            critical,
            ["warehouse_id", "product_id"],
        ].drop_duplicates()

        result = {
            "count": int(len(operational)),
            "high": int(len(high_pairs)),
            "critical": int(len(critical_pairs)),
        }
        _cache["stockout_risks"] = result
        return result

    result = {
        "count": int((high | critical).sum()),
        "high": int(high.sum()),
        "critical": int(critical.sum()),
    }
    _cache["stockout_risks"] = result
    return result


def _delivery_risks() -> dict:
    if _cache["delivery_risks"] is not _UNSET:
        return _cache["delivery_risks"]

    delivery = _read_csv(
        "delivery_risk_predictions.csv",
        usecols=["order_id", "risk_level"],
    )

    if delivery.empty or "risk_level" not in delivery.columns:
        result = {
            "count": 0,
            "high": 0,
            "critical": 0,
        }
        _cache["delivery_risks"] = result
        return result

    high = delivery["risk_level"].eq("High")
    critical = delivery["risk_level"].eq("Critical")

    if "order_id" in delivery.columns:
        high_orders = delivery.loc[
            high,
            "order_id",
        ].dropna().astype(str).drop_duplicates()

        critical_orders = delivery.loc[
            critical,
            "order_id",
        ].dropna().astype(str).drop_duplicates()

        risky_orders = delivery.loc[
            high | critical,
            "order_id",
        ].dropna().astype(str).drop_duplicates()

        result = {
            "count": int(len(risky_orders)),
            "high": int(len(high_orders)),
            "critical": int(len(critical_orders)),
        }
        _cache["delivery_risks"] = result
        return result

    result = {
        "count": int((high | critical).sum()),
        "high": int(high.sum()),
        "critical": int(critical.sum()),
    }
    _cache["delivery_risks"] = result
    return result


def _supplier_risks() -> dict:
    if _cache["supplier_risks"] is not _UNSET:
        return _cache["supplier_risks"]

    suppliers = _read_csv(
        "supplier_intelligence.csv",
        usecols=["risk_level", "supplier_id"],
    )

    if suppliers.empty or "risk_level" not in suppliers.columns:
        result = {
            "count": 0,
            "high": 0,
            "critical": 0,
        }
        _cache["supplier_risks"] = result
        return result

    high = suppliers["risk_level"].eq("High")
    critical = suppliers["risk_level"].eq("Critical")

    if "supplier_id" in suppliers.columns:
        risky = suppliers.loc[
            high | critical,
            "supplier_id",
        ].dropna().astype(str).drop_duplicates()

        result = {
            "count": int(len(risky)),
            "high": int(high.sum()),
            "critical": int(critical.sum()),
        }
        _cache["supplier_risks"] = result
        return result

    result = {
        "count": int((high | critical).sum()),
        "high": int(high.sum()),
        "critical": int(critical.sum()),
    }
    _cache["supplier_risks"] = result
    return result


def _daily_sales() -> pd.DataFrame:
    if _cache["daily_sales"] is not _UNSET:
        return _cache["daily_sales"]
    sales = _read_csv("daily_sales.csv", usecols=["revenue", "orders"])
    _cache["daily_sales"] = sales
    return sales


def _warm_caches_parallel() -> None:
    """Warm all summary caches in parallel on first (cold) request."""
    tasks = [
        _stockout_risks,
        _delivery_risks,
        _supplier_risks,
        _inventory_value,
        _daily_sales,
    ]
    with ThreadPoolExecutor(max_workers=min(len(tasks), 5)) as ex:
        list(ex.map(lambda fn: fn(), tasks))


@router.get("/summary")
def summary():
    if any(v is _UNSET for v in _cache.values()):
        _warm_caches_parallel()

    sales = _daily_sales()
    stockout = _stockout_risks()
    delivery = _delivery_risks()
    suppliers = _supplier_risks()
    forecast = _forecast_metrics()

    revenue = (
        float(sales["revenue"].sum())
        if not sales.empty and "revenue" in sales.columns
        else None
    )

    orders = (
        int(sales["orders"].sum())
        if not sales.empty and "orders" in sales.columns
        else None
    )

    optimization = repo.json("phase10_summary.json")

    optimization_savings = optimization.get("estimated_savings")

    if optimization_savings is not None:
        optimization_savings = float(optimization_savings)

    return {
        "revenue": revenue,
        "orders": orders,
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