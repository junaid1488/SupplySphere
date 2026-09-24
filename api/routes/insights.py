from fastapi import APIRouter
from api.services.data import DataRepository

router = APIRouter(prefix="/api", tags=["insights"])
repo = DataRepository()


@router.get("/insights")
def insights():
    stockout = repo.stockout()
    delivery = repo.delivery()
    suppliers = repo.suppliers()
    optimization = repo.optimization()
    inventory = repo.inventory()

    insights_list = []

    if not stockout.empty and "risk_level" in stockout.columns:
        high_stockout = stockout["risk_level"].eq("High")
        critical_stockout = stockout["risk_level"].eq("Critical")
        critical_count = int(critical_stockout.sum())
        high_count = int(high_stockout.sum())

        if critical_count > 0:
            insights_list.append({
                "category": "Inventory",
                "severity": "critical",
                "title": f"{critical_count} SKU(s) at Critical Stockout Risk",
                "description": f"{critical_count} product-warehouse combinations have critical stockout risk. Immediate replenishment required.",
                "action": "Review replenishment orders for affected SKUs",
                "count": critical_count,
            })
        if high_count > 0:
            insights_list.append({
                "category": "Inventory",
                "severity": "high",
                "title": f"{high_count} SKU(s) at High Stockout Risk",
                "description": f"{high_count} product-warehouse combinations have high stockout risk. Proactive replenishment recommended.",
                "action": "Schedule replenishment for affected SKUs",
                "count": high_count,
            })

    if not delivery.empty and "risk_level" in delivery.columns:
        high_delivery = delivery["risk_level"].eq("High")
        critical_delivery = delivery["risk_level"].eq("Critical")
        critical_count = int(critical_delivery.sum())
        high_count = int(high_delivery.sum())

        if critical_count > 0:
            insights_list.append({
                "category": "Logistics",
                "severity": "critical",
                "title": f"{critical_count} Shipment(s) at Critical Delivery Risk",
                "description": f"{critical_count} shipments have critical late delivery probability. Customer impact likely.",
                "action": "Expedite or reroute critical shipments",
                "count": critical_count,
            })
        if high_count > 0:
            insights_list.append({
                "category": "Logistics",
                "severity": "high",
                "title": f"{high_count} Shipment(s) at High Delivery Risk",
                "description": f"{high_count} shipments have elevated late delivery probability.",
                "action": "Monitor high-risk shipments closely",
                "count": high_count,
            })

    if not suppliers.empty and "risk_level" in suppliers.columns:
        high_supplier = suppliers["risk_level"].eq("High")
        critical_supplier = suppliers["risk_level"].eq("Critical")
        critical_count = int(critical_supplier.sum())
        high_count = int(high_supplier.sum())

        if critical_count > 0:
            insights_list.append({
                "category": "Suppliers",
                "severity": "critical",
                "title": f"{critical_count} Supplier(s) at Critical Risk",
                "description": f"{critical_count} suppliers flagged with critical risk. Supply continuity may be affected.",
                "action": "Engage backup suppliers for critical categories",
                "count": critical_count,
            })
        if high_count > 0:
            insights_list.append({
                "category": "Suppliers",
                "severity": "high",
                "title": f"{high_count} Supplier(s) at High Risk",
                "description": f"{high_count} suppliers flagged with elevated risk.",
                "action": "Review supplier performance and diversification",
                "count": high_count,
            })

    if optimization and optimization.get("status") == "OPTIMAL":
        savings = optimization.get("estimated_savings")
        service_level = optimization.get("service_level")
        stockout_risk = optimization.get("stockout_risk")

        if savings is not None and savings > 0:
            insights_list.append({
                "category": "Optimization",
                "severity": "info",
                "title": f"Optimization Identified ${savings:,.2f} Potential Savings",
                "description": f"Network optimization suggests {optimization.get('solver', 'solver')} can reduce costs while maintaining {service_level * 100:.1f}% service level.",
                "action": "Review and implement recommended transfers",
                "count": 1,
            })
        elif savings is not None and savings < 0:
            insights_list.append({
                "category": "Optimization",
                "severity": "warning",
                "title": "Optimization Shows Cost Increase",
                "description": f"Current configuration may be near-optimal. Estimated change: ${savings:,.2f}.",
                "action": "Validate constraints and demand forecasts",
                "count": 1,
            })

        if stockout_risk is not None and stockout_risk > 0.05:
            insights_list.append({
                "category": "Optimization",
                "severity": "high",
                "title": f"Optimized Network Shows {stockout_risk * 100:.1f}% Stockout Risk",
                "description": "Proposed optimization increases stockout risk above 5%.",
                "action": "Adjust service level constraints or safety stock",
                "count": 1,
            })

    if not inventory.empty:
        latest_date = inventory["snapshot_date"].max() if "snapshot_date" in inventory.columns else None
        if latest_date:
            latest = inventory[inventory["snapshot_date"] == latest_date]
            total_on_hand = latest["on_hand"].sum() if "on_hand" in latest.columns else 0
            zero_stock = int((latest["on_hand"] == 0).sum()) if "on_hand" in latest.columns else 0

            if zero_stock > 0:
                insights_list.append({
                    "category": "Inventory",
                    "severity": "high",
                    "title": f"{zero_stock} SKU(s) with Zero On-Hand Inventory",
                    "description": f"As of {latest_date}, {zero_stock} SKUs show zero available stock across warehouses.",
                    "action": "Verify stock positions and trigger emergency orders",
                    "count": zero_stock,
                })

    if not insights_list:
        insights_list.append({
            "category": "System",
            "severity": "info",
            "title": "No Operational Insights at This Time",
            "description": "All monitored metrics are within normal thresholds.",
            "action": "Continue monitoring",
            "count": 0,
        })

    return {
        "items": insights_list,
        "total": len(insights_list),
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }