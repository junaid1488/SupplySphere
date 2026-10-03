from fastapi import APIRouter
from api.services.data import DataRepository

router = APIRouter(prefix="/api", tags=["reports"])
repo = DataRepository()


@router.get("/reports")
def reports():
    # Streaming helpers: repo.stockout() / repo.inventory() each materialise a
    # 3.16 M row frame (~1 GB peak) and OOM-kill the 512 MiB Render worker.
    stockout_totals = repo.stockout_risk_totals()
    delivery = repo.delivery()
    suppliers = repo.suppliers()
    optimization = repo.optimization()
    inventory_stats = repo.inventory_snapshot_stats()
    forecast = repo.forecast()
    daily_sales = repo._read('daily_sales.csv')

    report = {
        "summary": {},
        "inventory_risk": {},
        "delivery_risk": {},
        "supplier_risk": {},
        "forecast_performance": {},
        "optimization_result": {},
        "operational_metrics": {},
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }

    if not daily_sales.empty:
        revenue = float(daily_sales["revenue"].sum()) if "revenue" in daily_sales.columns else None
        orders = int(daily_sales["orders"].sum()) if "orders" in daily_sales.columns else None
        report["summary"]["revenue"] = revenue
        report["summary"]["orders"] = orders

    if stockout_totals["total"] > 0:
        report["inventory_risk"] = {
            "total_at_risk": int(stockout_totals["high"] + stockout_totals["critical"]),
            "high": int(stockout_totals["high"]),
            "critical": int(stockout_totals["critical"]),
        }

    if not delivery.empty and "risk_level" in delivery.columns:
        high = delivery["risk_level"].eq("High")
        critical = delivery["risk_level"].eq("Critical")
        report["delivery_risk"] = {
            "total_at_risk": int((high | critical).sum()),
            "high": int(high.sum()),
            "critical": int(critical.sum()),
        }

    if not suppliers.empty and "risk_level" in suppliers.columns:
        high = suppliers["risk_level"].eq("High")
        critical = suppliers["risk_level"].eq("Critical")
        report["supplier_risk"] = {
            "total_at_risk": int((high | critical).sum()),
            "high": int(high.sum()),
            "critical": int(critical.sum()),
        }

    forecast_metrics = repo.forecast_metrics()
    if forecast_metrics:
        report["forecast_performance"] = {
            "selected_model": forecast_metrics.get("selected_model"),
            "wape": forecast_metrics.get("wape"),
            "smape": forecast_metrics.get("smape"),
            "mae": forecast_metrics.get("mae"),
            "rmse": forecast_metrics.get("rmse"),
            "accuracy": forecast_metrics.get("accuracy"),
        }
    elif not forecast.empty:
        report["forecast_performance"] = {
            "records": len(forecast),
            "products_forecasted": int(forecast["product_id"].nunique()) if "product_id" in forecast.columns else 0,
        }

    if optimization:
        report["optimization_result"] = {
            "solver": optimization.get("solver"),
            "status": optimization.get("status"),
            "current_cost": optimization.get("current_cost"),
            "optimized_cost": optimization.get("optimized_cost"),
            "estimated_savings": optimization.get("estimated_savings"),
            "service_level": optimization.get("service_level"),
            "stockout_risk": optimization.get("stockout_risk"),
            "transfers_recommended": optimization.get("transfer_rows"),
        }

    if inventory_stats:
        report["operational_metrics"] = {
            "latest_snapshot_date": inventory_stats.get("latest_snapshot_date"),
            "total_on_hand": inventory_stats.get("total_on_hand"),
            "zero_stock_skus": inventory_stats.get("zero_stock_skus"),
            "unique_products": inventory_stats.get("unique_products"),
            "unique_warehouses": inventory_stats.get("unique_warehouses"),
        }

    return report