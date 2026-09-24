from __future__ import annotations

import pandas as pd


FEATURES = [
    "lag_1",
    "lag_7",
    "rolling_mean_7",
    "rolling_std_7",
    "trend_7",
    "dow",
    "month",
    "product_frequency",
]


def build_demand_features(daily_demand: pd.DataFrame) -> pd.DataFrame:
    """
    Build leakage-safe demand features for the sparse Olist demand series.

    Expected columns:
        date
        product_id
        demand
    """
    required = {"date", "product_id", "demand"}
    missing = required - set(daily_demand.columns)

    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    df = daily_demand.copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    ).dt.floor("D")

    df["product_id"] = df["product_id"].astype(str)

    df["demand"] = pd.to_numeric(
        df["demand"],
        errors="coerce",
    ).fillna(0.0)

    df = (
        df.dropna(subset=["date", "product_id"])
        .groupby(["product_id", "date"], as_index=False)["demand"]
        .sum()
        .sort_values(["product_id", "date"])
        .reset_index(drop=True)
    )

    # ---------------------------------------------------------
    # Historical lags
    # ---------------------------------------------------------
    grouped = df.groupby("product_id", sort=False)

    df["lag_1"] = grouped["demand"].shift(1)
    df["lag_7"] = grouped["demand"].shift(7)

    # ---------------------------------------------------------
    # Historical rolling statistics
    #
    # shift(1) ensures today's demand is never used to predict today.
    # ---------------------------------------------------------
    shifted = grouped["demand"].shift(1)

    df["rolling_mean_7"] = (
        shifted.groupby(df["product_id"], sort=False)
        .transform(
            lambda s: s.rolling(
                window=7,
                min_periods=1,
            ).mean()
        )
    )

    df["rolling_std_7"] = (
        shifted.groupby(df["product_id"], sort=False)
        .transform(
            lambda s: s.rolling(
                window=7,
                min_periods=2,
            ).std()
        )
        .fillna(0.0)
    )

    short_mean = (
        shifted.groupby(df["product_id"], sort=False)
        .transform(
            lambda s: s.rolling(
                window=3,
                min_periods=1,
            ).mean()
        )
    )

    df["trend_7"] = (
        df["rolling_mean_7"] - short_mean
    )

    # ---------------------------------------------------------
    # Calendar features
    # ---------------------------------------------------------
    df["dow"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month

    # ---------------------------------------------------------
    # Leakage-safe expanding historical mean
    # ---------------------------------------------------------
    df["product_frequency"] = (
        shifted.groupby(df["product_id"], sort=False)
        .transform(
            lambda s: s.expanding(
                min_periods=1
            ).mean()
        )
        .fillna(0.0)
    )

    return df.reset_index(drop=True)


def make_supervised(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the supervised next-observation demand target.

    The target is the next recorded demand observation for the same product.
    """
    required = {"date", "product_id", "demand", *FEATURES}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns for supervised dataset: {sorted(missing)}"
        )

    x = (
        df.copy()
        .sort_values(["product_id", "date"])
        .reset_index(drop=True)
    )

    x["target"] = (
        x.groupby("product_id")["demand"]
        .shift(-1)
    )

    x = x.dropna(
        subset=FEATURES + ["target"]
    )

    return x.reset_index(drop=True)