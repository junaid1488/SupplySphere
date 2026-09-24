from pathlib import Path
import sys
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.settings import settings
from ml.delivery.model import (
    build_delivery_dataset,
    DeliveryRiskModel,
)


def main():
    staging = settings.staging_data_dir
    processed = settings.processed_data_dir
    models = settings.model_dir

    processed.mkdir(
        parents=True,
        exist_ok=True,
    )

    models.mkdir(
        parents=True,
        exist_ok=True,
    )

    orders = pd.read_csv(
        staging / "orders.csv"
    )

    items = pd.read_csv(
        staging / "order_items.csv"
    )

    products = pd.read_csv(
        staging / "products.csv"
    )

    sellers = pd.read_csv(
        staging / "sellers.csv"
    )

    customers = pd.read_csv(
        staging / "customers.csv"
    )

    geolocation = pd.read_csv(
        staging / "geolocation.csv"
    )

    delivery_data = build_delivery_dataset(
        orders,
        items,
        products,
        sellers,
        customers,
        geolocation,
    )

    delivery_data.to_csv(
        processed / "delivery_risk_features.csv",
        index=False,
    )

    model = DeliveryRiskModel(
        models
    )

    metrics, selected_model = model.train(
        delivery_data
    )

    predictions = model.predict(
        delivery_data
    )

    predictions.to_csv(
        processed / "delivery_risk_predictions.csv",
        index=False,
    )

    summary = {
        "selected_model": selected_model,
        "metrics": metrics,
        "rows": len(delivery_data),
        "positive_rate": float(
            delivery_data["late"].mean()
        ),
        "target": "late",
        "target_definition": (
            "Delivered orders where actual delivery "
            "date is later than estimated delivery date."
        ),
    }

    summary_path = (
        processed
        / "phase9_summary.json"
    )

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
        )
    )

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()