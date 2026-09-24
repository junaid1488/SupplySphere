from pathlib import Path
import json

import pandas as pd

from configs.settings import settings
from ml.stockout.model import (
    build_stockout_dataset,
    StockoutModel,
    risk_level,
)
from ml.suppliers.intelligence import (
    build_supplier_intelligence,
)
from ml.warehouses.intelligence import (
    warehouse_metrics,
    recommend_allocation,
    transfer_recommendations,
)
from ml.delivery.model import (
    build_delivery_dataset,
    DeliveryRiskModel,
)
from ml.optimization.model import SupplyOptimizer


PR = settings.processed_data_dir
ST = settings.staging_data_dir


def test_phase6_artifacts_and_risk_labels():
    df = pd.read_csv(
        PR / "stockout_features.csv"
    )

    assert len(df) > 1000

    assert {
        "stockout",
        "days_of_cover",
        "forecast_7d",
    }.issubset(df.columns)

    assert set(
        df.stockout.unique()
    ).issubset({0, 1})

    assert [
        risk_level(x)
        for x in [0, 0.3, 0.6, 0.85]
    ] == [
        "Low",
        "Medium",
        "High",
        "Critical",
    ]

    assert (
        PR / "stockout_model.joblib"
    ).exists() or (
        settings.model_dir
        / "stockout_model.joblib"
    ).exists()


def test_phase7_supplier_scores():
    df = pd.read_csv(
        PR / "supplier_intelligence.csv"
    )

    assert len(df) == 50

    assert df.supplier_score.between(
        0,
        100,
    ).all()

    assert set(
        df.risk_level
    ).issubset(
        {
            "Low",
            "Medium",
            "High",
            "Critical",
        }
    )


def test_phase8_warehouse_outputs():
    wm = pd.read_csv(
        PR / "warehouse_metrics.csv"
    )

    alloc = pd.read_csv(
        PR / "recommended_inventory_by_warehouse.csv"
    )

    assert len(wm) == 12

    assert wm.utilization.notna().all()

    assert (
        wm.utilization >= 0
    ).all()

    expected_utilization = (
        wm.inventory_units
        / wm.capacity_units
    )

    assert (
        abs(
            wm.utilization
            - expected_utilization
        )
        < 1e-9
    ).all()

    assert len(alloc) > 0

    assert (
        alloc.recommended_inventory
        .ge(0)
        .all()
    )


def test_phase9_delivery_artifacts():
    df = pd.read_csv(
        PR / "delivery_risk_features.csv"
    )

    pred = pd.read_csv(
        PR / "delivery_risk_predictions.csv"
    )

    assert len(df) > 50000

    assert len(pred) == len(df)

    assert {
        "late_delivery_probability",
        "risk_level",
        "expected_delivery_date",
    }.issubset(
        pred.columns
    )

    summary = json.loads(
        (
            PR
            / "phase6_10_summary.json"
        ).read_text()
    )

    assert summary["phase9"][
        "selected_model"
    ] in {
        "LogisticRegression",
        "RandomForest",
        "XGBoost",
    }


def test_phase10_optimization_contract():
    result = SupplyOptimizer().solve(
        pd.read_csv(
            PR / "suppliers.csv"
        ),
        pd.read_csv(
            PR / "warehouses.csv"
        ),
        pd.read_csv(
            PR / "stockout_features.csv"
        ),
        pd.read_csv(
            PR / "inventory_snapshots.csv"
        ),
    )

    assert (
        result.service_level >= 0
        and result.service_level <= 1
    )

    assert (
        result.stockout_risk >= 0
        and result.stockout_risk <= 1
    )

    assert result.solver in {
        "greedy_fallback",
        "OR-Tools CBC",
    }

    assert result.optimized_cost >= 0