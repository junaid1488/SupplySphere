from pathlib import Path
import sys
import json

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.settings import settings
from ml.optimization.model import SupplyOptimizer


def main():
    processed = settings.processed_data_dir
    processed.mkdir(parents=True, exist_ok=True)

    suppliers = pd.read_csv(processed / "suppliers.csv")
    warehouses = pd.read_csv(processed / "warehouses.csv")
    inventory = pd.read_csv(processed / "inventory_snapshots.csv")
    supplier_products = pd.read_csv(processed / "supplier_products.csv")

    demand = pd.read_csv(
        processed / "stockout_features.csv",
        usecols=[
            "snapshot_date",
            "warehouse_id",
            "product_id",
            "forecast_7d",
        ],
    )

    demand["snapshot_date"] = pd.to_datetime(
        demand["snapshot_date"],
        errors="coerce",
    )

    latest_demand_date = demand["snapshot_date"].max()

    if pd.isna(latest_demand_date):
        raise ValueError(
            "No valid snapshot_date found in stockout_features.csv."
        )

    demand = demand[
        demand["snapshot_date"] == latest_demand_date
    ].copy()

    required_supplier_columns = {
        "supplier_id",
        "capacity_units",
        "unit_cost",
        "moq",
        "lead_time_days",
        "reliability",
    }

    required_supplier_product_columns = {
        "supplier_id",
        "product_id",
    }

    required_warehouse_columns = {
        "warehouse_id",
        "capacity_units",
        "operating_cost_per_unit",
    }

    required_inventory_columns = {
        "snapshot_date",
        "warehouse_id",
        "product_id",
        "on_hand",
        "reserved",
    }

    missing_suppliers = (
        required_supplier_columns - set(suppliers.columns)
    )

    missing_supplier_products = (
        required_supplier_product_columns
        - set(supplier_products.columns)
    )

    missing_warehouses = (
        required_warehouse_columns - set(warehouses.columns)
    )

    missing_inventory = (
        required_inventory_columns - set(inventory.columns)
    )

    if missing_suppliers:
        raise ValueError(
            f"Missing supplier columns: {sorted(missing_suppliers)}"
        )

    if missing_supplier_products:
        raise ValueError(
            "Missing supplier-product columns: "
            f"{sorted(missing_supplier_products)}"
        )

    if missing_warehouses:
        raise ValueError(
            f"Missing warehouse columns: {sorted(missing_warehouses)}"
        )

    if missing_inventory:
        raise ValueError(
            f"Missing inventory columns: {sorted(missing_inventory)}"
        )

    demand["forecast_7d"] = pd.to_numeric(
        demand["forecast_7d"],
        errors="coerce",
    ).fillna(0.0)

    demand = demand.dropna(
        subset=[
            "warehouse_id",
            "product_id",
        ]
    ).copy()

    demand["warehouse_id"] = (
        demand["warehouse_id"]
        .astype(str)
        .str.strip()
    )

    demand["product_id"] = (
        demand["product_id"]
        .astype(str)
        .str.strip()
    )

    demand = demand[
        demand["forecast_7d"] > 0
    ].copy()

    if demand.empty:
        raise ValueError(
            "Latest Phase 10 demand dataset is empty."
        )

    if suppliers["supplier_id"].duplicated().any():
        raise ValueError(
            "Duplicate supplier_id values detected."
        )

    if warehouses["warehouse_id"].duplicated().any():
        raise ValueError(
            "Duplicate warehouse_id values detected."
        )

    if supplier_products.duplicated(
        subset=[
            "supplier_id",
            "product_id",
        ]
    ).any():
        raise ValueError(
            "Duplicate supplier-product relationships detected."
        )

    optimizer = SupplyOptimizer(
        time_limit_ms=30000,
    )

    result = optimizer.solve(
        suppliers,
        warehouses,
        demand,
        inventory,
    )

    supplier_output = result.supplier_quantities.copy()
    warehouse_output = result.warehouse_quantities.copy()
    transfer_output = result.transfers.copy()

    supplier_path = (
        processed
        / "optimization_supplier_quantities.csv"
    )

    warehouse_path = (
        processed
        / "optimization_warehouse_quantities.csv"
    )

    transfer_path = (
        processed
        / "optimization_transfers.csv"
    )

    summary_path = (
        processed
        / "phase10_summary.json"
    )

    supplier_output.to_csv(
        supplier_path,
        index=False,
    )

    warehouse_output.to_csv(
        warehouse_path,
        index=False,
    )

    transfer_output.to_csv(
        transfer_path,
        index=False,
    )

    summary = {
        "phase": 10,
        "status": result.status,
        "solver": result.solver,
        "current_cost": float(
            result.current_cost
        ),
        "optimized_cost": float(
            result.optimized_cost
        ),
        "estimated_savings": float(
            result.current_cost
            - result.optimized_cost
        ),
        "service_level": float(
            result.service_level
        ),
        "stockout_risk": float(
            result.stockout_risk
        ),
        "supplier_rows": int(
            len(supplier_output)
        ),
        "warehouse_rows": int(
            len(warehouse_output)
        ),
        "transfer_rows": int(
            len(transfer_output)
        ),
        "supplier_count": int(
            suppliers["supplier_id"].nunique()
        ),
        "supplier_product_relationships": int(
            len(supplier_products)
        ),
        "warehouse_count": int(
            warehouses["warehouse_id"].nunique()
        ),
        "demand_rows": int(
            len(demand)
        ),
        "inventory_rows": int(
            len(inventory)
        ),
        "demand_snapshot_date": (
            latest_demand_date.strftime("%Y-%m-%d")
        ),
        "time_limit_ms": 30000,
    }

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()