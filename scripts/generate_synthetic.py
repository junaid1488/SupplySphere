from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from configs.settings import settings
from src.synthetic.generator import SyntheticGenerator


if __name__ == "__main__":
    products_path = settings.staging_data_dir / "products.csv"
    orders_path = settings.staging_data_dir / "orders.csv"
    demand_path = settings.processed_data_dir / "daily_product_demand.csv"

    if not products_path.exists():
        raise FileNotFoundError(
            "Run ingestion first; products.csv is required."
        )

    if not demand_path.exists():
        raise FileNotFoundError(
            "daily_product_demand.csv is required. "
            "Run the analytics pipeline first."
        )

    products = pd.read_csv(products_path)

    orders = (
        pd.read_csv(orders_path)
        if orders_path.exists()
        else pd.DataFrame(columns=["order_id"])
    )

    demand = pd.read_csv(demand_path)

    generator = SyntheticGenerator(settings.synthetic_seed)

    warehouses = generator.warehouses()
    suppliers = generator.suppliers()

    outputs = {
        "warehouses": warehouses,
        "suppliers": suppliers,
        "supplier_products": generator.supplier_products(
            suppliers,
            products,
        ),
        "inventory_snapshots": generator.inventory(
            products,
            warehouses,
            demand=demand,
        ),
        "purchase_orders": generator.purchase_orders(
            suppliers,
            products,
        ),
        "warehouse_transfers": generator.transfers(
            warehouses,
        ),
        "shipment_events": generator.shipment_events(
            orders,
        ),
    }

    settings.processed_data_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for name, df in outputs.items():
        df.to_csv(
            settings.processed_data_dir / f"{name}.csv",
            index=False,
        )

        print(
            f"{name}: {len(df):,} rows"
        )

    print(
        f"Generated {len(outputs)} deterministic synthetic datasets."
    )