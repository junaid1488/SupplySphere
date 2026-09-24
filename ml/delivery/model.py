from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier


NUM = [
    "freight_value",
    "distance_km",
    "days_to_estimate",
    "seller_historical_delay",
    "seller_order_count",
    "seller_freight_mean",
    "seller_distance_mean",
]

CAT = [
    "seller_id",
    "product_category",
    "customer_state",
]

FEATURES = NUM + CAT


def haversine(
    lat1,
    lon1,
    lat2,
    lon2,
):
    lat1, lon1, lat2, lon2 = map(
        np.radians,
        [lat1, lon1, lat2, lon2],
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    return 6371.0 * 2 * np.arcsin(
        np.sqrt(np.clip(a, 0, 1))
    )


def _validate_columns(df, required):
    missing = sorted(set(required) - set(df.columns))

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )


def _build_geolocation_lookup(geolocation):
    g = geolocation.copy()

    _validate_columns(
        g,
        [
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
        ],
    )

    g["geolocation_lat"] = pd.to_numeric(
        g["geolocation_lat"],
        errors="coerce",
    )

    g["geolocation_lng"] = pd.to_numeric(
        g["geolocation_lng"],
        errors="coerce",
    )

    g = g.dropna(
        subset=[
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
        ]
    )

    return g.groupby(
        "geolocation_zip_code_prefix",
        as_index=True,
    )[["geolocation_lat", "geolocation_lng"]].mean()


def _seller_history(df):
    x = df.sort_values(
        [
            "order_purchase_timestamp",
            "order_id",
        ]
    ).copy()

    seller = x["seller_id"]

    prior_count = (
        x.groupby("seller_id", sort=False)
        .cumcount()
    )

    prior_late_sum = (
        x["late"]
        .groupby(seller, sort=False)
        .transform(
            lambda s: s.shift(1)
            .expanding()
            .sum()
        )
    )

    prior_freight_sum = (
        x["freight_value"]
        .groupby(seller, sort=False)
        .transform(
            lambda s: s.shift(1)
            .expanding()
            .sum()
        )
    )

    prior_distance_sum = (
        x["distance_km"]
        .groupby(seller, sort=False)
        .transform(
            lambda s: s.shift(1)
            .expanding()
            .sum()
        )
    )

    prior_late_sum = prior_late_sum.fillna(0.0)
    prior_freight_sum = prior_freight_sum.fillna(0.0)
    prior_distance_sum = prior_distance_sum.fillna(0.0)

    global_rate = float(
        x["late"].mean()
    )

    x["seller_order_count"] = prior_count

    x["seller_historical_delay"] = np.where(
        prior_count > 0,
        prior_late_sum / prior_count,
        global_rate,
    )

    x["seller_freight_mean"] = np.where(
        prior_count > 0,
        prior_freight_sum / prior_count,
        x["freight_value"].median(),
    )

    x["seller_distance_mean"] = np.where(
        prior_count > 0,
        prior_distance_sum / prior_count,
        x["distance_km"].median(),
    )

    return x


def build_delivery_dataset(
    orders,
    items,
    products,
    sellers,
    customers,
    geolocation,
):
    o = orders.copy()
    i = items.copy()
    p = products.copy()
    s = sellers.copy()
    c = customers.copy()

    required_order_columns = [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]

    _validate_columns(
        o,
        required_order_columns,
    )

    for col in [
        "order_purchase_timestamp",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]:
        o[col] = pd.to_datetime(
            o[col],
            errors="coerce",
        )

    i["freight_value"] = pd.to_numeric(
        i["freight_value"],
        errors="coerce",
    ).fillna(0.0)

    item_order = (
        i.groupby("order_id")
        .agg(
            freight_value=(
                "freight_value",
                "sum",
            ),
            seller_id=(
                "seller_id",
                "nunique",
            ),
            product_id=(
                "product_id",
                "nunique",
            ),
        )
        .reset_index()
        .rename(
            columns={
                "seller_id": "seller_count",
                "product_id": "product_count",
            }
        )
    )

    primary_item = (
        i.sort_values(
            [
                "order_id",
                "order_item_id",
            ]
        )
        .drop_duplicates(
            "order_id",
            keep="first",
        )[
            [
                "order_id",
                "seller_id",
                "product_id",
            ]
        ]
    )

    item_order = item_order.merge(
        primary_item,
        on="order_id",
        how="left",
    )

    x = (
        o.merge(
            item_order,
            on="order_id",
            how="inner",
        )
        .merge(
            p[
                [
                    "product_id",
                    "product_category_name",
                ]
            ],
            on="product_id",
            how="left",
        )
        .rename(
            columns={
                "product_category_name":
                    "product_category"
            }
        )
        .merge(
            s[
                [
                    "seller_id",
                    "seller_zip_code_prefix",
                ]
            ],
            on="seller_id",
            how="left",
        )
        .merge(
            c[
                [
                    "customer_id",
                    "customer_zip_code_prefix",
                    "customer_state",
                ]
            ],
            on="customer_id",
            how="left",
        )
    )

    geo = _build_geolocation_lookup(
        geolocation
    )

    seller_geo = geo.rename(
        columns={
            "geolocation_lat": "slat",
            "geolocation_lng": "slon",
        }
    )

    customer_geo = geo.rename(
        columns={
            "geolocation_lat": "clat",
            "geolocation_lng": "clon",
        }
    )

    x = x.join(
        seller_geo,
        on="seller_zip_code_prefix",
    )

    x = x.join(
        customer_geo,
        on="customer_zip_code_prefix",
    )

    valid_geo = (
        x["slat"].notna()
        & x["slon"].notna()
        & x["clat"].notna()
        & x["clon"].notna()
    )

    x["distance_km"] = np.nan

    x.loc[valid_geo, "distance_km"] = haversine(
        x.loc[valid_geo, "slat"],
        x.loc[valid_geo, "slon"],
        x.loc[valid_geo, "clat"],
        x.loc[valid_geo, "clon"],
    )

    x["days_to_estimate"] = (
        x["order_estimated_delivery_date"]
        - x["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400.0

    x["delivery_days"] = (
        x["order_delivered_customer_date"]
        - x["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400.0

    eligible = (
        x["order_delivered_customer_date"].notna()
        & x["order_estimated_delivery_date"].notna()
    )

    x["late"] = np.nan

    x.loc[eligible, "late"] = (
        x.loc[
            eligible,
            "order_delivered_customer_date",
        ]
        > x.loc[
            eligible,
            "order_estimated_delivery_date",
        ]
    ).astype(int)

    x = x[
        x["order_status"].eq("delivered")
        & x["late"].notna()
    ].copy()

    x["late"] = x["late"].astype(int)

    x = _seller_history(x)

    x["seller_order_count"] = x[
        "seller_order_count"
    ].astype(float)

    x["product_category"] = (
        x["product_category"]
        .fillna("unknown")
        .astype(str)
    )

    return x.reset_index(drop=True)


class DeliveryRiskModel:

    def __init__(
        self,
        model_dir: Path,
    ):
        self.model_dir = Path(model_dir)

        self.model_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _pipeline(
        self,
        estimator,
    ):
        prep = ColumnTransformer(
            [
                (
                    "num",
                    Pipeline(
                        [
                            (
                                "imp",
                                SimpleImputer(
                                    strategy="median"
                                ),
                            ),
                            (
                                "scale",
                                StandardScaler(),
                            ),
                        ]
                    ),
                    NUM,
                ),
                (
                    "cat",
                    Pipeline(
                        [
                            (
                                "imp",
                                SimpleImputer(
                                    strategy="most_frequent"
                                ),
                            ),
                            (
                                "oh",
                                OneHotEncoder(
                                    handle_unknown="ignore"
                                ),
                            ),
                        ]
                    ),
                    CAT,
                ),
            ]
        )

        return Pipeline(
            [
                ("prep", prep),
                ("model", estimator),
            ]
        )

    @staticmethod
    def _metrics(
        y_true,
        probability,
    ):
        prediction = probability >= 0.5

        return {
            "precision": float(
                precision_score(
                    y_true,
                    prediction,
                    zero_division=0,
                )
            ),
            "recall": float(
                recall_score(
                    y_true,
                    prediction,
                    zero_division=0,
                )
            ),
            "f1": float(
                f1_score(
                    y_true,
                    prediction,
                    zero_division=0,
                )
            ),
            "roc_auc": float(
                roc_auc_score(
                    y_true,
                    probability,
                )
            ),
            "pr_auc": float(
                average_precision_score(
                    y_true,
                    probability,
                )
            ),
        }

    def train(self, df):
        required = [
            "order_purchase_timestamp",
            "late",
        ] + FEATURES

        _validate_columns(
            df,
            required,
        )

        x = df.sort_values(
            [
                "order_purchase_timestamp",
                "order_id",
            ]
        ).reset_index(drop=True)

        x = x.dropna(
            subset=["late"]
        ).copy()

        if x["late"].nunique() != 2:
            raise ValueError(
                "Delivery-risk target must contain both classes."
            )

        split = int(
            len(x) * 0.80
        )

        if split <= 0 or split >= len(x):
            raise ValueError(
                "Invalid temporal train/test split."
            )

        train = x.iloc[:split].copy()
        test = x.iloc[split:].copy()

        if train["late"].nunique() != 2:
            raise ValueError(
                "Training split does not contain both classes."
            )

        if test["late"].nunique() != 2:
            raise ValueError(
                "Test split does not contain both classes."
            )

        y_train = train["late"].astype(int)
        y_test = test["late"].astype(int)

        candidates = {
            "LogisticRegression":
                LogisticRegression(
                    max_iter=1200,
                    class_weight="balanced",
                    random_state=42,
                ),
            "RandomForest":
                RandomForestClassifier(
                    n_estimators=160,
                    max_depth=12,
                    min_samples_leaf=4,
                    class_weight="balanced_subsample",
                    random_state=42,
                    n_jobs=2,
                ),
            "XGBoost":
                XGBClassifier(
                    n_estimators=160,
                    max_depth=5,
                    learning_rate=0.05,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    eval_metric="logloss",
                    random_state=42,
                    n_jobs=2,
                ),
        }

        scores = {}
        fitted = {}

        for name, estimator in candidates.items():
            pipeline = self._pipeline(
                estimator
            )

            pipeline.fit(
                train[FEATURES],
                y_train,
            )

            probability = pipeline.predict_proba(
                test[FEATURES]
            )[:, 1]

            scores[name] = self._metrics(
                y_test,
                probability,
            )

            fitted[name] = pipeline

        winner = max(
            scores,
            key=lambda name: (
                scores[name]["pr_auc"],
                scores[name]["f1"],
                scores[name]["recall"],
            ),
        )

        artifact = {
            "model": fitted[winner],
            "features": FEATURES,
            "metrics": scores,
            "selected_model": winner,
            "target": "late",
            "target_definition": (
                "Delivered orders where actual delivery "
                "date is later than estimated delivery date."
            ),
            "split": {
                "type": "chronological",
                "train_fraction": 0.80,
            },
            "notes": [
                "Seller historical features use only prior orders.",
                "Geolocation distance is missing when either endpoint "
                "has no valid coordinates.",
                "Training target is based on completed historical "
                "Olist orders.",
                "Predictions represent delivery-delay probability "
                "under the historical Olist distribution.",
            ],
        }

        joblib.dump(
            artifact,
            self.model_dir
            / "delivery_risk_model.joblib",
        )

        return scores, winner

    def load(self):
        path = (
            self.model_dir
            / "delivery_risk_model.joblib"
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Model artifact not found: {path}"
            )

        return joblib.load(path)

    def predict(self, df):
        artifact = self.load()

        features = artifact["features"]

        _validate_columns(
            df,
            features,
        )

        probability = artifact[
            "model"
        ].predict_proba(
            df[features]
        )[:, 1]

        probability = np.clip(
            probability,
            0.0,
            1.0,
        )

        out = pd.DataFrame(
            {
                "order_id": df[
                    "order_id"
                ].values,
                "late_delivery_probability":
                    probability,
            }
        )

        out["risk_level"] = pd.cut(
            probability,
            bins=[
                -0.01,
                0.30,
                0.60,
                0.85,
                1.00,
            ],
            labels=[
                "Low",
                "Medium",
                "High",
                "Critical",
            ],
        ).astype(str)

        purchase = pd.to_datetime(
            df[
                "order_purchase_timestamp"
            ],
            errors="coerce",
        )

        estimate = pd.to_datetime(
            df[
                "order_estimated_delivery_date"
            ],
            errors="coerce",
        )

        base_days = (
            estimate - purchase
        ).dt.total_seconds() / 86400.0

        historical_delay_days = (
            df[
                "seller_historical_delay"
            ]
            .fillna(0.0)
            .clip(0.0, 1.0)
            * 3.0
        )

        additional_days = (
            probability * 5.0
            + historical_delay_days
        )

        expected = (
            estimate
            + pd.to_timedelta(
                additional_days,
                unit="D",
            )
        )

        expected = expected.where(
            base_days >= 0,
            purchase,
        )

        out[
            "expected_delivery_date"
        ] = expected

        return out