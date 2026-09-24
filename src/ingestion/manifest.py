from pathlib import Path
import pandas as pd

EXPECTED = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

def discover(raw_dir: Path) -> dict[str, Path]:
    found = {}
    for key, filename in EXPECTED.items():
        path = raw_dir / filename
        if path.exists():
            found[key] = path
    return found

def inspect_file(path: Path) -> dict:
    df = pd.read_csv(path, low_memory=False)
    return {
        "file": path.name,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "dtypes": {k: str(v) for k, v in df.dtypes.items()},
        "null_counts": {k: int(v) for k, v in df.isna().sum().items() if int(v)},
        "duplicate_rows": int(df.duplicated().sum()),
        "candidate_primary_keys": [c for c in df.columns if df[c].is_unique and not df[c].isna().any()],
        "date_columns": [c for c in df.columns if "date" in c.lower()],
        "geographic_columns": [c for c in df.columns if any(x in c.lower() for x in ["zip", "city", "state", "lat", "lng", "longitude", "latitude"])],
    }

def build_data_dictionary(raw_dir: Path) -> dict:
    return {name: inspect_file(path) for name, path in discover(raw_dir).items()}
