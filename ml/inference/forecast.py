from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd


class ForecastInference:
    """
    Demand forecast inference for the persisted Phase 5 artifact.

    Supports:
        7-day
        30-day
        90-day

    For the current Olist training target (next observed demand),
    baseline forecasts use product-specific historical demand.
    """

    ALLOWED_HORIZONS = {7, 30, 90}

    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Forecast model artifact not found: {self.model_path}"
            )

        artifact = joblib.load(self.model_path)

        self.model = artifact.get("model")
        self.features = artifact["features"]
        self.selected_model = artifact.get(
            "selected_model",
            "Naive",
        )
        self.model_type = artifact.get(
            "model_type",
            "baseline",
        )
        self.target = artifact.get(
            "target",
            "next_observed_demand",
        )

        self.evaluation = artifact.get(
            "evaluation",
            {},
        )

    @staticmethod
    def _product_history(
        features: pd.DataFrame,
        product_id: str,
    ) -> np.ndarray:
        required = {"product_id", "date", "demand"}

        missing = required - set(features.columns)

        if missing:
            raise ValueError(
                f"Missing columns: {sorted(missing)}"
            )

        history = (
            features.loc[
                features["product_id"].astype(str) == str(product_id)
            ]
            .sort_values("date")["demand"]
            .astype(float)
            .to_numpy()
        )

        return history

    def _baseline_forecast(
        self,
        features: pd.DataFrame,
        product_id: str,
        horizon: int,
    ) -> np.ndarray:

        history = self._product_history(
            features,
            product_id,
        )

        if len(history) == 0:
            return np.zeros(horizon, dtype=float)

        if self.selected_model == "Naive":
            value = float(history[-1])

        elif self.selected_model == "Moving Average":
            value = float(
                np.mean(history[-7:])
            )

        else:
            raise ValueError(
                f"Unsupported baseline model: "
                f"{self.selected_model}"
            )

        return np.repeat(
            max(0.0, value),
            horizon,
        )

    def predict(
        self,
        features: pd.DataFrame,
        horizon: int = 7,
        product_id: str | None = None,
    ) -> pd.Series:

        if horizon not in self.ALLOWED_HORIZONS:
            raise ValueError(
                "horizon must be one of 7, 30, or 90 days"
            )

        if len(features) == 0:
            raise ValueError(
                "At least one feature row is required."
            )

        frame = features.copy()

        frame["date"] = pd.to_datetime(
            frame["date"],
            errors="coerce",
        )

        if product_id is not None:
            product_id = str(product_id)

            frame = frame[
                frame["product_id"].astype(str)
                == product_id
            ].copy()

            if frame.empty:
                raise ValueError(
                    f"No feature history found for "
                    f"product_id={product_id}"
                )

        # -----------------------------------------------------
        # Baseline inference
        # -----------------------------------------------------

        if self.model_type == "baseline":
            if product_id is None:
                raise ValueError(
                    "product_id is required for "
                    "product-specific baseline inference."
                )

            predictions = self._baseline_forecast(
                frame,
                product_id,
                horizon,
            )

            return pd.Series(
                predictions,
                name="forecast",
            )

        # -----------------------------------------------------
        # ML inference
        # -----------------------------------------------------

        if self.model is None:
            raise ValueError(
                "Artifact contains no ML model."
            )

        missing = set(self.features) - set(frame.columns)

        if missing:
            raise ValueError(
                f"Forecast feature frame is missing: "
                f"{sorted(missing)}"
            )

        frame = (
            frame.sort_values("date")
            .reset_index(drop=True)
        )

        latest = frame.tail(1)

        if latest.empty:
            raise ValueError(
                "No valid feature row available."
            )

        # The current ML artifact is trained for next-observed
        # demand. Future feature generation is therefore deliberately
        # conservative until a dedicated future-feature service exists.
        future_rows = []

        current = latest.copy()

        for step in range(horizon):
            prediction = float(
                self.model.predict(
                    current[self.features]
                )[0]
            )

            prediction = max(
                0.0,
                prediction,
            )

            future_rows.append(prediction)

            current = current.copy()

            current["date"] = (
                pd.to_datetime(current["date"])
                + pd.Timedelta(days=1)
            )

            current["lag_7"] = current["lag_1"]
            current["lag_1"] = prediction

            current["rolling_mean_7"] = (
                current["rolling_mean_7"] * 6
                + prediction
            ) / 7

            current["rolling_std_7"] = (
                current["rolling_std_7"]
            )

            current["trend_7"] = (
                current["rolling_mean_7"]
                - current["rolling_mean_7"]
            )

            current["dow"] = (
                current["date"].dt.dayofweek
            )

            current["month"] = (
                current["date"].dt.month
            )

            current["product_frequency"] = (
                current["product_frequency"] * 0.99
                + prediction * 0.01
            )

        return pd.Series(
            np.asarray(
                future_rows,
                dtype=float,
            ),
            name="forecast",
        )