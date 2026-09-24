from __future__ import annotations

import numpy as np
import pandas as pd


def naive_forecast(history, horizon: int):
    """
    Forecast the last observed demand value.
    """
    history = np.asarray(history, dtype=float)

    if horizon < 1:
        raise ValueError("horizon must be at least 1.")

    value = float(history[-1]) if len(history) else 0.0

    return np.repeat(value, horizon)


def moving_average_forecast(
    history,
    horizon: int,
    window: int = 7,
):
    """
    Forecast using the mean of the most recent observations.
    """
    history = np.asarray(history, dtype=float)

    if horizon < 1:
        raise ValueError("horizon must be at least 1.")

    if window < 1:
        raise ValueError("window must be at least 1.")

    if len(history):
        value = float(np.mean(history[-window:]))
    else:
        value = 0.0

    return np.repeat(value, horizon)


def evaluate_product_baseline(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    method: str,
    window: int = 7,
) -> np.ndarray:
    """
    Generate product-aware baseline predictions.

    Each product gets its own historical baseline rather than sharing
    one global demand value across all products.

    Required columns:
        product_id
        target
    """
    required = {"product_id", "target"}

    if not required.issubset(train.columns):
        raise ValueError(
            f"Training data must contain {sorted(required)}."
        )

    if not required.issubset(validation.columns):
        raise ValueError(
            f"Validation data must contain {sorted(required)}."
        )

    history = (
        train.groupby("product_id")["target"]
        .apply(lambda s: s.astype(float).to_numpy())
        .to_dict()
    )

    predictions = []

    for _, row in validation.iterrows():
        product_id = row["product_id"]
        values = history.get(product_id, np.array([], dtype=float))

        if method == "Naive":
            prediction = naive_forecast(values, 1)[0]

        elif method == "Moving Average":
            prediction = moving_average_forecast(
                values,
                1,
                window=window,
            )[0]

        else:
            raise ValueError(
                f"Unsupported baseline method: {method}"
            )

        predictions.append(float(prediction))

    return np.asarray(predictions, dtype=float)