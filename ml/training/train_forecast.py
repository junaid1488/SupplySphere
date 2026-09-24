from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from xgboost import XGBRegressor

from ml.evaluation.metrics import evaluate
from ml.features.demand import FEATURES, make_supervised


class ForecastTrainer:

    def __init__(self, model_dir: Path):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _temporal_split(
        data: pd.DataFrame,
        validation_fraction: float = 0.2,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:

        dates = (
            pd.to_datetime(data["date"])
            .dropna()
            .sort_values()
            .unique()
        )

        if len(dates) < 2:
            raise ValueError(
                "At least two distinct dates are required."
            )

        cutoff_index = max(
            int(len(dates) * (1.0 - validation_fraction)),
            1,
        )

        cutoff_index = min(
            cutoff_index,
            len(dates) - 1,
        )

        cutoff_date = dates[cutoff_index]

        train = data[data["date"] < cutoff_date].copy()
        validation = data[data["date"] >= cutoff_date].copy()

        if train.empty or validation.empty:
            raise ValueError(
                "Temporal split produced an empty dataset."
            )

        return train, validation

    @staticmethod
    def _product_baseline(
        train: pd.DataFrame,
        validation: pd.DataFrame,
        method: str,
        window: int = 7,
    ) -> np.ndarray:

        histories = (
            train.sort_values(["product_id", "date"])
            .groupby("product_id")["demand"]
            .apply(lambda s: s.astype(float).to_numpy())
            .to_dict()
        )

        global_history = train["demand"].astype(float).to_numpy()

        predictions = []

        for product_id in validation["product_id"]:
            history = histories.get(
                product_id,
                global_history,
            )

            if len(history) == 0:
                prediction = 0.0

            elif method == "Naive":
                prediction = float(history[-1])

            elif method == "Moving Average":
                prediction = float(
                    np.mean(history[-window:])
                )

            else:
                raise ValueError(
                    f"Unsupported baseline: {method}"
                )

            predictions.append(
                max(0.0, prediction)
            )

        return np.asarray(
            predictions,
            dtype=float,
        )

    @staticmethod
    def _build_models() -> dict[str, Any]:

        return {
            "GradientBoosting": HistGradientBoostingRegressor(
                max_iter=250,
                learning_rate=0.05,
                max_leaf_nodes=15,
                random_state=42,
            ),
            "XGBoost": XGBRegressor(
                n_estimators=250,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="reg:squarederror",
                random_state=42,
                n_jobs=2,
            ),
            "LightGBM": LGBMRegressor(
                n_estimators=250,
                num_leaves=31,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                random_state=42,
                n_jobs=2,
                verbosity=-1,
            ),
        }

    def train(
        self,
        feature_df: pd.DataFrame,
        validation_fraction: float = 0.2,
    ):

        data = make_supervised(feature_df)

        if len(data) < 20:
            raise ValueError(
                "At least 20 supervised rows are required."
            )

        data["date"] = pd.to_datetime(data["date"])

        data = (
            data
            .sort_values(["date", "product_id"])
            .reset_index(drop=True)
        )

        train, validation = self._temporal_split(
            data,
            validation_fraction,
        )

        X_train = train[FEATURES]
        y_train = train["target"]

        X_validation = validation[FEATURES]
        y_validation = validation["target"]

        scores = {}
        models = self._build_models()

        # -----------------------------
        # Product-aware baselines
        # -----------------------------

        naive_pred = self._product_baseline(
            train,
            validation,
            "Naive",
        )

        scores["Naive"] = evaluate(
            y_validation,
            naive_pred,
        )

        moving_pred = self._product_baseline(
            train,
            validation,
            "Moving Average",
        )

        scores["Moving Average"] = evaluate(
            y_validation,
            moving_pred,
        )

        # -----------------------------
        # ML models
        # -----------------------------

        for name, model in models.items():

            model.fit(
                X_train,
                y_train,
            )

            prediction = model.predict(
                X_validation,
            )

            prediction = np.maximum(
                prediction,
                0.0,
            )

            scores[name] = evaluate(
                y_validation,
                prediction,
            )

        # -----------------------------
        # Model selection
        # -----------------------------

        selected_model = min(
            scores,
            key=lambda name: (
                scores[name]["WAPE"],
                scores[name]["sMAPE"],
                scores[name]["MAE"],
                name,
            ),
        )

        selected_estimator = models.get(
            selected_model
        )

        artifact = {
            "artifact_version": 3,
            "model": selected_estimator,
            "model_type": (
                "machine_learning"
                if selected_estimator is not None
                else "baseline"
            ),
            "selected_model": selected_model,
            "features": FEATURES,
            "evaluation": scores,
            "target": "next_observed_demand",
            "training_rows": int(len(train)),
            "validation_rows": int(len(validation)),
            "training_start": train["date"].min().isoformat(),
            "training_end": train["date"].max().isoformat(),
            "validation_start": validation["date"].min().isoformat(),
            "validation_end": validation["date"].max().isoformat(),
            "validation_fraction": validation_fraction,
            "non_negative_forecast": True,
        }

        output = (
            self.model_dir
            / "demand_forecast.joblib"
        )

        joblib.dump(
            artifact,
            output,
        )

        return scores, selected_model

    def load(self) -> dict[str, Any]:

        path = (
            self.model_dir
            / "demand_forecast.joblib"
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Forecast model artifact not found: {path}"
            )

        return joblib.load(path)