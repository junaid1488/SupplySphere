from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


CORE_COLUMNS = {
    "customers": [
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    ],
    "orders": [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "sellers": [
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    ],
    "products": [
        "product_id",
        "product_category_name",
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ],
    "order_items": [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    ],
    "payments": [
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    ],
    "reviews": [
        "review_id",
        "order_id",
        "review_score",
        "review_comment_title",
        "review_comment_message",
        "review_creation_date",
        "review_answer_timestamp",
    ],
    "geolocation": [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ],
}


DATETIME_COLUMNS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": [
        "shipping_limit_date",
    ],
    "reviews": [
        "review_creation_date",
        "review_answer_timestamp",
    ],
}


LOAD_ORDER = [
    "customers",
    "sellers",
    "products",
    "orders",
    "order_items",
    "payments",
    "reviews",
    "geolocation",
]

CLEAR_ORDER = list(reversed(LOAD_ORDER))


def _clean(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Normalize staged data before loading it into PostgreSQL."""

    df = df.copy()

    # Convert only columns that are actually defined as datetime
    # for the corresponding core table.
    for col in DATETIME_COLUMNS.get(table_name, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def rebuild_core_from_staging(
    engine: Engine,
    staging_dir: Path,
) -> dict[str, int]:
    """Idempotently rebuild core from the staged Olist CSVs."""

    counts: dict[str, int] = {}

    with engine.begin() as conn:

        # Clear existing core data in dependency-safe order.
        for name in CLEAR_ORDER:
            conn.execute(
                text(
                    f'TRUNCATE TABLE core."{name}" '
                    "RESTART IDENTITY CASCADE"
                )
            )

        # Load staged datasets in dependency-safe order.
        for name in LOAD_ORDER:
            path = Path(staging_dir) / f"{name}.csv"

            if not path.exists():
                raise FileNotFoundError(
                    f"Missing staged dataset: {path}"
                )

            df = pd.read_csv(
                path,
                low_memory=False,
            )

            df = _clean(df, name)

            cols = [
                c
                for c in CORE_COLUMNS[name]
                if c in df.columns
            ]

            df = df[cols]

            df.to_sql(
                name,
                conn,
                schema="core",
                if_exists="append",
                index=False,
                method="multi",
                chunksize=1000,
            )

            counts[name] = len(df)

    return counts