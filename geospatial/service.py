from __future__ import annotations

from functools import lru_cache
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

import pandas as pd


# Original India operational network (pre-Brazil), recovered from
# service.cpython-314.pyc + data/processed/warehouses.csv +
# src/synthetic/network.py. IDs WH-001..WH-012, 12 nodes → 132 routes.
INDIA_NETWORK: list[dict[str, object]] = [
    {"warehouse_id": "WH-001", "warehouse_name": "Delhi", "city": "Delhi", "state": None, "latitude": 28.6139, "longitude": 77.209},
    {"warehouse_id": "WH-002", "warehouse_name": "Mumbai", "city": "Mumbai", "state": None, "latitude": 19.076, "longitude": 72.8777},
    {"warehouse_id": "WH-003", "warehouse_name": "Bengaluru", "city": "Bengaluru", "state": None, "latitude": 12.9716, "longitude": 77.5946},
    {"warehouse_id": "WH-004", "warehouse_name": "Hyderabad", "city": "Hyderabad", "state": None, "latitude": 17.385, "longitude": 78.4867},
    {"warehouse_id": "WH-005", "warehouse_name": "Chennai", "city": "Chennai", "state": None, "latitude": 13.0827, "longitude": 80.2707},
    {"warehouse_id": "WH-006", "warehouse_name": "Kolkata", "city": "Kolkata", "state": None, "latitude": 22.5726, "longitude": 88.3639},
    {"warehouse_id": "WH-007", "warehouse_name": "Lucknow", "city": "Lucknow", "state": None, "latitude": 26.8467, "longitude": 80.9462},
    {"warehouse_id": "WH-008", "warehouse_name": "Jaipur", "city": "Jaipur", "state": None, "latitude": 26.9124, "longitude": 75.7873},
    {"warehouse_id": "WH-009", "warehouse_name": "Pune", "city": "Pune", "state": None, "latitude": 18.5204, "longitude": 73.8567},
    {"warehouse_id": "WH-010", "warehouse_name": "Ahmedabad", "city": "Ahmedabad", "state": None, "latitude": 23.0225, "longitude": 72.5714},
    {"warehouse_id": "WH-011", "warehouse_name": "Patna", "city": "Patna", "state": None, "latitude": 25.5941, "longitude": 85.1376},
    {"warehouse_id": "WH-012", "warehouse_name": "Guwahati", "city": "Guwahati", "state": None, "latitude": 26.1445, "longitude": 91.7362},
]


def _network_nodes(network: str) -> list[dict[str, object]]:
    if network == "india":
        return INDIA_NETWORK
    return BRAZIL_NETWORK


# Synthetic demo warehouse network — not native Olist warehouse data.
# Operational planning nodes only; IDs WH-001..WH-015 retained so existing
# processed CSV joins (inventory/demand/transfers) stay valid.
BRAZIL_NETWORK: list[dict[str, object]] = [
    {"warehouse_id": "WH-001", "warehouse_name": "São Paulo Hub", "city": "São Paulo", "state": "SP", "latitude": -23.5505, "longitude": -46.6333},
    {"warehouse_id": "WH-002", "warehouse_name": "Rio de Janeiro Hub", "city": "Rio de Janeiro", "state": "RJ", "latitude": -22.9068, "longitude": -43.1729},
    {"warehouse_id": "WH-003", "warehouse_name": "Belo Horizonte Hub", "city": "Belo Horizonte", "state": "MG", "latitude": -19.9167, "longitude": -43.9345},
    {"warehouse_id": "WH-004", "warehouse_name": "Curitiba Hub", "city": "Curitiba", "state": "PR", "latitude": -25.4284, "longitude": -49.2733},
    {"warehouse_id": "WH-005", "warehouse_name": "Porto Alegre Hub", "city": "Porto Alegre", "state": "RS", "latitude": -30.0346, "longitude": -51.2177},
    {"warehouse_id": "WH-006", "warehouse_name": "Brasília Hub", "city": "Brasília", "state": "DF", "latitude": -15.7939, "longitude": -47.8828},
    {"warehouse_id": "WH-007", "warehouse_name": "Goiânia Hub", "city": "Goiânia", "state": "GO", "latitude": -16.6869, "longitude": -49.2648},
    {"warehouse_id": "WH-008", "warehouse_name": "Salvador Hub", "city": "Salvador", "state": "BA", "latitude": -12.9777, "longitude": -38.5016},
    {"warehouse_id": "WH-009", "warehouse_name": "Recife Hub", "city": "Recife", "state": "PE", "latitude": -8.0476, "longitude": -34.8770},
    {"warehouse_id": "WH-010", "warehouse_name": "Fortaleza Hub", "city": "Fortaleza", "state": "CE", "latitude": -3.7319, "longitude": -38.5267},
    {"warehouse_id": "WH-011", "warehouse_name": "Manaus Hub", "city": "Manaus", "state": "AM", "latitude": -3.1190, "longitude": -60.0217},
    {"warehouse_id": "WH-012", "warehouse_name": "Belém Hub", "city": "Belém", "state": "PA", "latitude": -1.4558, "longitude": -48.4902},
    {"warehouse_id": "WH-013", "warehouse_name": "Campinas Hub", "city": "Campinas", "state": "SP", "latitude": -22.9099, "longitude": -47.0626},
    {"warehouse_id": "WH-014", "warehouse_name": "Ribeirão Preto Hub", "city": "Ribeirão Preto", "state": "SP", "latitude": -21.1704, "longitude": -47.8103},
    {"warehouse_id": "WH-015", "warehouse_name": "Vitória Hub", "city": "Vitória", "state": "ES", "latitude": -20.3155, "longitude": -40.3128},
]

# Backward-compatible alias: default/legacy callers keep the current
# Brazil synthetic demo network.
NETWORK = BRAZIL_NETWORK


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    radius = 6371.0088

    phi1 = radians(float(lat1))
    phi2 = radians(float(lat2))
    delta_phi = radians(float(lat2) - float(lat1))
    delta_lambda = radians(float(lon2) - float(lon1))

    value = (
        sin(delta_phi / 2) ** 2
        + cos(phi1)
        * cos(phi2)
        * sin(delta_lambda / 2) ** 2
    )

    return 2 * radius * atan2(
        sqrt(value),
        sqrt(max(1 - value, 0)),
    )


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _clean_records(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    result = df.copy()

    for column in result.columns:
        if pd.api.types.is_datetime64_any_dtype(result[column]):
            result[column] = result[column].dt.strftime("%Y-%m-%d")

    return result.where(result.notna(), None)


@lru_cache(maxsize=4)
def _geolocation_lookup(raw_dir_string: str) -> pd.DataFrame:
    raw_dir = Path(raw_dir_string)
    path = raw_dir / "olist_geolocation_dataset.csv"

    if not path.exists():
        return _empty(
            [
                "zip_code_prefix",
                "latitude",
                "longitude",
                "geo_city",
                "geo_state",
            ]
        )

    geo = pd.read_csv(
        path,
        usecols=[
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ],
    )

    geo = geo.rename(
        columns={
            "geolocation_zip_code_prefix": "zip_code_prefix",
            "geolocation_lat": "latitude",
            "geolocation_lng": "longitude",
            "geolocation_city": "geo_city",
            "geolocation_state": "geo_state",
        }
    )

    geo["zip_code_prefix"] = pd.to_numeric(
        geo["zip_code_prefix"],
        errors="coerce",
    )

    geo["latitude"] = pd.to_numeric(
        geo["latitude"],
        errors="coerce",
    )

    geo["longitude"] = pd.to_numeric(
        geo["longitude"],
        errors="coerce",
    )

    geo = geo.dropna(
        subset=[
            "zip_code_prefix",
            "latitude",
            "longitude",
        ]
    )

    geo["zip_code_prefix"] = geo["zip_code_prefix"].astype(int)

    return (
        geo.groupby("zip_code_prefix", as_index=False)
        .agg(
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
            geo_city=("geo_city", "first"),
            geo_state=("geo_state", "first"),
        )
    )


def _attach_coordinates(
    frame: pd.DataFrame,
    raw_dir: Path,
    zip_column: str,
) -> pd.DataFrame:
    if frame.empty:
        return frame

    geo = _geolocation_lookup(str(raw_dir))

    result = frame.copy()

    result[zip_column] = pd.to_numeric(
        result[zip_column],
        errors="coerce",
    )

    result = result.merge(
        geo,
        left_on=zip_column,
        right_on="zip_code_prefix",
        how="left",
    )

    result = result.drop(columns=["zip_code_prefix"], errors="ignore")

    return result


def warehouse_features(network: str = "brazil") -> pd.DataFrame:
    return pd.DataFrame(_network_nodes(network))


def customer_points(
    raw_dir: Path,
    limit: int = 1000,
    return_total: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, int]:
    path = Path(raw_dir) / "olist_customers_dataset.csv"

    if not path.exists():
        empty = _empty(
            [
                "customer_id",
                "customer_unique_id",
                "zip_code_prefix",
                "city",
                "state",
                "latitude",
                "longitude",
            ]
        )
        return (empty, 0) if return_total else empty

    customers = pd.read_csv(
        path,
        usecols=[
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ],
    )

    customers = customers.rename(
        columns={
            "customer_zip_code_prefix": "zip_code_prefix",
            "customer_city": "city",
            "customer_state": "state",
        }
    )

    customers = _attach_coordinates(
        customers,
        Path(raw_dir),
        "zip_code_prefix",
    )

    customers = customers.dropna(
        subset=["latitude", "longitude"]
    )

    total = len(customers)
    if return_total:
        return customers.head(limit), total
    return customers.head(limit)


def seller_points(
    raw_dir: Path,
    limit: int = 1000,
) -> pd.DataFrame:
    path = Path(raw_dir) / "olist_sellers_dataset.csv"

    if not path.exists():
        return _empty(
            [
                "seller_id",
                "zip_code_prefix",
                "city",
                "state",
                "latitude",
                "longitude",
            ]
        )

    sellers = pd.read_csv(
        path,
        usecols=[
            "seller_id",
            "seller_zip_code_prefix",
            "seller_city",
            "seller_state",
        ],
    )

    sellers = sellers.rename(
        columns={
            "seller_zip_code_prefix": "zip_code_prefix",
            "seller_city": "city",
            "seller_state": "state",
        }
    )

    sellers = _attach_coordinates(
        sellers,
        Path(raw_dir),
        "zip_code_prefix",
    )

    sellers = sellers.dropna(
        subset=["latitude", "longitude"]
    )

    return sellers.head(limit)


def order_points(
    raw_dir: Path,
    limit: int = 1000,
) -> pd.DataFrame:
    orders_path = Path(raw_dir) / "olist_orders_dataset.csv"
    customers_path = Path(raw_dir) / "olist_customers_dataset.csv"

    if not orders_path.exists() or not customers_path.exists():
        return _empty(
            [
                "order_id",
                "customer_id",
                "order_status",
                "purchase_date",
                "city",
                "state",
                "latitude",
                "longitude",
            ]
        )

    orders = pd.read_csv(
        orders_path,
        usecols=[
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
        ],
    )

    customers = pd.read_csv(
        customers_path,
        usecols=[
            "customer_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ],
    )

    customers = customers.rename(
        columns={
            "customer_zip_code_prefix": "zip_code_prefix",
            "customer_city": "city",
            "customer_state": "state",
        }
    )

    orders = orders.merge(
        customers,
        on="customer_id",
        how="left",
    )

    orders = _attach_coordinates(
        orders,
        Path(raw_dir),
        "zip_code_prefix",
    )

    orders["purchase_date"] = pd.to_datetime(
        orders["order_purchase_timestamp"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    orders = orders.dropna(
        subset=["latitude", "longitude"]
    )

    return orders[
        [
            "order_id",
            "customer_id",
            "order_status",
            "purchase_date",
            "city",
            "state",
            "latitude",
            "longitude",
        ]
    ].head(limit)


@lru_cache(maxsize=4)
def demand_points(
    processed_dir_str: str,
    raw_dir_str: str,
    limit: int = 2000,
) -> pd.DataFrame:
    processed_dir = Path(processed_dir_str)
    raw_dir = Path(raw_dir_str)
    stockout_path = (
        Path(processed_dir) / "stockout_features.csv"
    )

    if not stockout_path.exists():
        return _empty(
            [
                "warehouse_id",
                "product_id",
                "snapshot_date",
                "forecast_7d",
                "latitude",
                "longitude",
            ]
        )

    demand = pd.read_csv(
        stockout_path,
        usecols=[
            "snapshot_date",
            "warehouse_id",
            "product_id",
            "forecast_7d",
        ],
    )

    demand["snapshot_date"] = pd.to_datetime(
        demand["snapshot_date"],
        errors="coerce",
    )

    latest = demand["snapshot_date"].max()

    demand = demand[
        demand["snapshot_date"] == latest
    ].copy()

    demand["forecast_7d"] = pd.to_numeric(
        demand["forecast_7d"],
        errors="coerce",
    ).fillna(0)

    demand = demand[
        demand["forecast_7d"] > 0
    ]

    warehouses = warehouse_features()

    demand = demand.merge(
        warehouses,
        on="warehouse_id",
        how="left",
    )

    demand = demand[
        [
            "warehouse_id",
            "product_id",
            "snapshot_date",
            "forecast_7d",
            "latitude",
            "longitude",
        ]
    ]

    demand = demand.sort_values(
        "forecast_7d",
        ascending=False,
    )

    demand["snapshot_date"] = demand[
        "snapshot_date"
    ].dt.strftime("%Y-%m-%d")

    return demand.head(limit)


@lru_cache(maxsize=4)
def inventory_points(
    processed_dir_str: str,
    limit: int = 2000,
) -> pd.DataFrame:
    processed_dir = Path(processed_dir_str)
    path = (
        Path(processed_dir)
        / "inventory_snapshots.csv"
    )

    if not path.exists():
        return _empty(
            [
                "warehouse_id",
                "product_id",
                "snapshot_date",
                "on_hand",
                "reserved",
                "available_inventory",
                "latitude",
                "longitude",
            ]
        )

    inventory = pd.read_csv(
        path,
        usecols=[
            "snapshot_date",
            "warehouse_id",
            "product_id",
            "on_hand",
            "reserved",
        ],
    )

    inventory["snapshot_date"] = pd.to_datetime(
        inventory["snapshot_date"],
        errors="coerce",
    )

    latest = inventory["snapshot_date"].max()

    inventory = inventory[
        inventory["snapshot_date"] == latest
    ].copy()

    inventory["on_hand"] = pd.to_numeric(
        inventory["on_hand"],
        errors="coerce",
    ).fillna(0)

    inventory["reserved"] = pd.to_numeric(
        inventory["reserved"],
        errors="coerce",
    ).fillna(0)

    inventory["available_inventory"] = (
        inventory["on_hand"]
        - inventory["reserved"]
    ).clip(lower=0)

    inventory = inventory.merge(
        warehouse_features(),
        on="warehouse_id",
        how="left",
    )

    inventory = inventory.groupby(
        [
            "warehouse_id",
            "latitude",
            "longitude",
            "snapshot_date",
        ],
        as_index=False,
    ).agg(
        inventory_units=("on_hand", "sum"),
        reserved_units=("reserved", "sum"),
        available_inventory=(
            "available_inventory",
            "sum",
        ),
    )

    inventory["snapshot_date"] = inventory[
        "snapshot_date"
    ].dt.strftime("%Y-%m-%d")

    inventory = inventory.sort_values(
        "inventory_units",
        ascending=False,
    )

    return inventory.head(limit)


@lru_cache(maxsize=4)
def delivery_points(
    raw_dir_str: str,
    processed_dir_str: str,
    limit: int = 2000,
) -> pd.DataFrame:
    raw_dir = Path(raw_dir_str)
    processed_dir = Path(processed_dir_str)
    prediction_path = (
        Path(processed_dir)
        / "delivery_risk_predictions.csv"
    )

    orders_path = (
        Path(raw_dir)
        / "olist_orders_dataset.csv"
    )

    customers_path = (
        Path(raw_dir)
        / "olist_customers_dataset.csv"
    )

    if (
        not prediction_path.exists()
        or not orders_path.exists()
        or not customers_path.exists()
    ):
        return _empty(
            [
                "order_id",
                "late_delivery_probability",
                "risk_level",
                "expected_delivery_date",
                "latitude",
                "longitude",
            ]
        )

    predictions = pd.read_csv(
        prediction_path
    )

    if "order_id" not in predictions.columns:
        return _empty(
            [
                "order_id",
                "late_delivery_probability",
                "risk_level",
                "expected_delivery_date",
                "latitude",
                "longitude",
            ]
        )

    predictions = predictions[
        [
            "order_id",
            "late_delivery_probability",
            "risk_level",
            "expected_delivery_date",
        ]
    ]

    orders = pd.read_csv(
        orders_path,
        usecols=[
            "order_id",
            "customer_id",
        ],
    )

    customers = pd.read_csv(
        customers_path,
        usecols=[
            "customer_id",
            "customer_zip_code_prefix",
        ],
    )

    customers = customers.rename(
        columns={
            "customer_zip_code_prefix":
                "zip_code_prefix"
        }
    )

    result = (
        predictions
        .merge(orders, on="order_id", how="inner")
        .merge(customers, on="customer_id", how="left")
    )

    result = _attach_coordinates(
        result,
        Path(raw_dir),
        "zip_code_prefix",
    )

    result = result.dropna(
        subset=["latitude", "longitude"]
    )

    result["late_delivery_probability"] = (
        pd.to_numeric(
            result["late_delivery_probability"],
            errors="coerce",
        ).fillna(0)
    )

    result = result.sort_values(
        "late_delivery_probability",
        ascending=False,
    )

    return result[
        [
            "order_id",
            "late_delivery_probability",
            "risk_level",
            "expected_delivery_date",
            "latitude",
            "longitude",
        ]
    ].head(limit)


def supplier_points(
    processed_dir: Path,
) -> pd.DataFrame:
    path = (
        Path(processed_dir)
        / "supplier_intelligence.csv"
    )

    if not path.exists():
        return _empty(
            [
                "supplier_id",
                "supplier_name",
                "supplier_score",
                "risk_score",
                "risk_level",
            ]
        )

    columns = [
        "supplier_id",
        "supplier_name",
        "supplier_score",
        "risk_score",
        "risk_level",
    ]

    available = pd.read_csv(
        path,
        nrows=1,
    ).columns.tolist()

    columns = [
        column
        for column in columns
        if column in available
    ]

    return pd.read_csv(
        path,
        usecols=columns,
    )


def transfer_points(
    processed_dir: Path,
    limit: int = 2000,
    network: str = "brazil",
) -> pd.DataFrame:
    path = (
        Path(processed_dir)
        / "optimization_transfers.csv"
    )

    if not path.exists():
        return _empty(
            [
                "product_id",
                "origin",
                "destination",
                "quantity",
                "status",
                "origin_latitude",
                "origin_longitude",
                "destination_latitude",
                "destination_longitude",
                "distance_km",
            ]
        )

    transfers = pd.read_csv(path)

    required = [
        "product_id",
        "origin",
        "destination",
        "quantity",
        "status",
    ]

    if not all(
        column in transfers.columns
        for column in required
    ):
        return _empty(
            required
            + [
                "origin_latitude",
                "origin_longitude",
                "destination_latitude",
                "destination_longitude",
                "distance_km",
            ]
        )

    coordinates = warehouse_features(network).rename(
        columns={
            "warehouse_id": "warehouse"
        }
    )

    origin = coordinates.rename(
        columns={
            "warehouse": "origin",
            "latitude": "origin_latitude",
            "longitude": "origin_longitude",
        }
    )

    destination = coordinates.rename(
        columns={
            "warehouse": "destination",
            "latitude": "destination_latitude",
            "longitude": "destination_longitude",
        }
    )

    transfers = (
        transfers
        .merge(
            origin[
                [
                    "origin",
                    "origin_latitude",
                    "origin_longitude",
                ]
            ],
            on="origin",
            how="left",
        )
        .merge(
            destination[
                [
                    "destination",
                    "destination_latitude",
                    "destination_longitude",
                ]
            ],
            on="destination",
            how="left",
        )
    )

    transfers["distance_km"] = transfers.apply(
        lambda row: (
            haversine_km(
                row["origin_latitude"],
                row["origin_longitude"],
                row["destination_latitude"],
                row["destination_longitude"],
            )
            if pd.notna(row["origin_latitude"])
            and pd.notna(row["destination_latitude"])
            else None
        ),
        axis=1,
    )

    transfers = transfers.sort_values(
        "quantity",
        ascending=False,
    )

    transfers = transfers.reset_index(drop=True)
    transfers.insert(
        0,
        "transfer_id",
        [f"TR-{index:04d}" for index in range(1, len(transfers) + 1)],
    )
    transfers["source_warehouse_id"] = transfers["origin"]
    transfers["destination_warehouse_id"] = transfers["destination"]
    transfers["source_latitude"] = transfers["origin_latitude"]
    transfers["source_longitude"] = transfers["origin_longitude"]

    return transfers.head(limit)


def route_table(network: str = "brazil") -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    nodes = _network_nodes(network)

    for origin in nodes:
        for destination in nodes:
            if origin["warehouse_id"] == destination["warehouse_id"]:
                continue

            rows.append(
                {
                    "origin_warehouse_id": origin["warehouse_id"],
                    "destination_warehouse_id": destination["warehouse_id"],
                    "origin_city": origin["city"],
                    "destination_city": destination["city"],
                    "origin_latitude": origin["latitude"],
                    "origin_longitude": origin["longitude"],
                    "destination_latitude": destination["latitude"],
                    "destination_longitude": destination["longitude"],
                    "distance_km": round(
                        haversine_km(
                            origin["latitude"],
                            origin["longitude"],
                            destination["latitude"],
                            destination["longitude"],
                        ),
                        2,
                    ),
                }
            )

    return pd.DataFrame(rows)


@lru_cache(maxsize=4)
def _shipping_lanes_frame(raw_dir_string: str) -> pd.DataFrame:
    raw_dir = Path(raw_dir_string)

    orders_path = raw_dir / "olist_orders_dataset.csv"
    items_path = raw_dir / "olist_order_items_dataset.csv"
    sellers_path = raw_dir / "olist_sellers_dataset.csv"
    customers_path = raw_dir / "olist_customers_dataset.csv"

    columns = [
        "order_id",
        "order_item_id",
        "seller_id",
        "customer_id",
        "seller_zip_code_prefix",
        "customer_zip_code_prefix",
        "origin_latitude",
        "origin_longitude",
        "destination_latitude",
        "destination_longitude",
        "origin_city",
        "origin_state",
        "destination_city",
        "destination_state",
        "distance_km",
    ]

    if (
        not orders_path.exists()
        or not items_path.exists()
        or not sellers_path.exists()
        or not customers_path.exists()
    ):
        return _empty(columns)

    orders = pd.read_csv(
        orders_path,
        usecols=[
            "order_id",
            "customer_id",
        ],
    )

    items = pd.read_csv(
        items_path,
        usecols=[
            "order_id",
            "order_item_id",
            "seller_id",
        ],
    )

    sellers = pd.read_csv(
        sellers_path,
        usecols=[
            "seller_id",
            "seller_zip_code_prefix",
            "seller_city",
            "seller_state",
        ],
    )

    customers = pd.read_csv(
        customers_path,
        usecols=[
            "customer_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ],
    )

    lanes = (
        items
        .merge(orders, on="order_id", how="inner")
        .merge(sellers, on="seller_id", how="inner")
        .merge(customers, on="customer_id", how="inner")
    )

    lanes["seller_zip_code_prefix"] = pd.to_numeric(
        lanes["seller_zip_code_prefix"],
        errors="coerce",
    )

    lanes["customer_zip_code_prefix"] = pd.to_numeric(
        lanes["customer_zip_code_prefix"],
        errors="coerce",
    )

    geo = _geolocation_lookup(raw_dir_string)

    seller_geo = geo.rename(
        columns={
            "zip_code_prefix": "seller_zip_code_prefix",
            "latitude": "origin_latitude",
            "longitude": "origin_longitude",
        }
    )[
        [
            "seller_zip_code_prefix",
            "origin_latitude",
            "origin_longitude",
        ]
    ]

    customer_geo = geo.rename(
        columns={
            "zip_code_prefix": "customer_zip_code_prefix",
            "latitude": "destination_latitude",
            "longitude": "destination_longitude",
        }
    )[
        [
            "customer_zip_code_prefix",
            "destination_latitude",
            "destination_longitude",
        ]
    ]

    lanes = lanes.merge(
        seller_geo,
        on="seller_zip_code_prefix",
        how="left",
    )

    lanes = lanes.merge(
        customer_geo,
        on="customer_zip_code_prefix",
        how="left",
    )

    lanes = lanes.dropna(
        subset=[
            "origin_latitude",
            "origin_longitude",
            "destination_latitude",
            "destination_longitude",
        ]
    )

    lanes = lanes.rename(
        columns={
            "seller_city": "origin_city",
            "seller_state": "origin_state",
            "customer_city": "destination_city",
            "customer_state": "destination_state",
        }
    )

    lanes["distance_km"] = lanes.apply(
        lambda row: round(
            haversine_km(
                row["origin_latitude"],
                row["origin_longitude"],
                row["destination_latitude"],
                row["destination_longitude"],
            ),
            2,
        )
        if pd.notna(row["origin_latitude"])
        and pd.notna(row["origin_longitude"])
        and pd.notna(row["destination_latitude"])
        and pd.notna(row["destination_longitude"])
        else None,
        axis=1,
    )

    lanes = lanes[
        lanes["distance_km"].notna()
        & (lanes["distance_km"] >= 0)
    ]

    return lanes[columns].reset_index(drop=True)


def shipping_lanes(
    raw_dir: Path,
    limit: int | None = None,
    return_total: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, int]:
    frame = _shipping_lanes_frame(str(Path(raw_dir)))
    total = len(frame)
    result = frame if limit is None else frame.head(limit)
    if return_total:
        return result, total
    return result


def geospatial_summary(
    raw_dir: Path,
    processed_dir: Path,
) -> dict[str, object]:
    customers = customer_points(
        raw_dir,
        limit=1_000_000,
    )

    sellers = seller_points(
        raw_dir,
        limit=1_000_000,
    )

    orders = order_points(
        raw_dir,
        limit=1_000_000,
    )

    routes = route_table()

    return {
        "warehouses": len(BRAZIL_NETWORK),
        "india_warehouses": len(INDIA_NETWORK),
        "customers_mapped": int(len(customers)),
        "sellers_mapped": int(len(sellers)),
        "orders_mapped": int(len(orders)),
        "routes": int(len(routes)),
        "india_routes": int(len(route_table("india"))),
        "supplier_coordinates": False,
        "supplier_coordinate_reason": (
            "supplier_intelligence.csv does not "
            "contain geographic coordinates"
        ),
    }