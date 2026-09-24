from pathlib import Path

import numpy as np
import pandas as pd

from .network import INDIA_NETWORK


class SyntheticGenerator:
    def __init__(self, seed=42):
        self.rng = np.random.default_rng(seed)

    def warehouses(self, n=None):
        cities = (
            INDIA_NETWORK
            if n is None
            else INDIA_NETWORK[:n]
        )

        return pd.DataFrame(
            [
                {
                    "warehouse_id": f"WH-{i + 1:03d}",
                    "city": city.name,
                    "latitude": city.latitude,
                    "longitude": city.longitude,
                    "capacity_units": int(
                        self.rng.integers(
                            20000,
                            80000,
                        )
                    ),
                    "operating_cost_per_unit": round(
                        float(
                            self.rng.uniform(
                                1.5,
                                5.0,
                            )
                        ),
                        2,
                    ),
                }
                for i, city in enumerate(cities)
            ]
        )

    def inventory(
        self,
        products,
        warehouses,
        demand=None,
        snapshot_dates=None,
    ):
        if demand is None or demand.empty:
            raise ValueError(
                "Demand data is required."
            )

        d = demand.copy()

        date_col = (
            "demand_date"
            if "demand_date" in d.columns
            else "date"
        )

        demand_col = (
            "demand_units"
            if "demand_units" in d.columns
            else "demand"
        )

        required_columns = {
            "product_id",
            date_col,
            demand_col,
        }

        if not required_columns.issubset(
            d.columns
        ):
            raise ValueError(
                "Demand must contain product_id, "
                "date and demand columns."
            )

        d["demand_date"] = pd.to_datetime(
            d[date_col],
            errors="coerce",
        )

        d["product_id"] = (
            d["product_id"]
            .astype(str)
        )

        d[demand_col] = (
            pd.to_numeric(
                d[demand_col],
                errors="coerce",
            )
            .fillna(0.0)
        )

        d = d.dropna(
            subset=["demand_date"]
        )

        if snapshot_dates is None:
            start = (
                d["demand_date"].min()
                + pd.Timedelta(days=30)
            )

            end = (
                d["demand_date"].max()
                - pd.Timedelta(days=30)
            )

            if end <= start:
                end = d["demand_date"].max()

            snapshot_dates = pd.date_range(
                start,
                end,
                periods=8,
            )

        snapshot_dates = (
            pd.to_datetime(
                snapshot_dates
            )
            .normalize()
        )

        product_ids = (
            products["product_id"]
            .astype(str)
            .drop_duplicates()
            .to_numpy()
        )

        demand_grouped = (
            d.groupby(
                [
                    "demand_date",
                    "product_id",
                ],
                as_index=False,
            )[demand_col]
            .sum()
            .sort_values(
                [
                    "demand_date",
                    "product_id",
                ]
            )
        )

        rows = []

        for snapshot_date in snapshot_dates:
            historical = demand_grouped[
                demand_grouped["demand_date"]
                < snapshot_date
            ]

            daily_demand = (
                historical.groupby(
                    "product_id"
                )[demand_col]
                .sum()
                .div(30.0)
            )

            active = daily_demand[
                daily_demand > 0
            ]

            active_ids = (
                active.index
                .astype(str)
                .to_numpy()
            )

            active_values = (
                active.to_numpy(
                    dtype=float
                )
            )

            if len(active_ids) > 0:
                demand_weights = np.sqrt(
                    active_values + 0.01
                )

                weight_sum = (
                    demand_weights.sum()
                )

                if weight_sum > 0:
                    demand_weights /= (
                        weight_sum
                    )
            else:
                demand_weights = np.empty(
                    0,
                    dtype=float,
                )

            active_set = set(
                active_ids
            )

            inactive_ids = np.asarray(
                [
                    product_id
                    for product_id in product_ids
                    if product_id not in active_set
                ],
                dtype=str,
            )

            for warehouse in warehouses.itertuples(
                index=False
            ):
                capacity = int(
                    warehouse.capacity_units
                )

                maximum_allowed = int(
                    np.floor(
                        capacity * 0.90
                    )
                )

                target_utilization = float(
                    self.rng.uniform(
                        0.55,
                        0.85,
                    )
                )

                warehouse_target = min(
                    int(
                        np.floor(
                            capacity
                            * target_utilization
                        )
                    ),
                    maximum_allowed,
                )

                if len(active_ids) > 0:
                    allocations = (
                        demand_weights
                        * warehouse_target
                    )

                    regimes = self.rng.choice(
                        4,
                        size=len(active_ids),
                        p=[
                            0.10,
                            0.20,
                            0.50,
                            0.20,
                        ],
                    )

                    coverage = np.empty(
                        len(active_ids),
                        dtype=float,
                    )

                    critical_mask = (
                        regimes == 0
                    )

                    low_mask = (
                        regimes == 1
                    )

                    normal_mask = (
                        regimes == 2
                    )

                    high_mask = (
                        regimes == 3
                    )

                    coverage[
                        critical_mask
                    ] = self.rng.uniform(
                        0.5,
                        2.0,
                        critical_mask.sum(),
                    )

                    coverage[
                        low_mask
                    ] = self.rng.uniform(
                        2.0,
                        6.0,
                        low_mask.sum(),
                    )

                    coverage[
                        normal_mask
                    ] = self.rng.uniform(
                        7.0,
                        18.0,
                        normal_mask.sum(),
                    )

                    coverage[
                        high_mask
                    ] = self.rng.uniform(
                        18.0,
                        35.0,
                        high_mask.sum(),
                    )

                    demand_inventory = (
                        active_values
                        * coverage
                    )

                    base_inventory = np.minimum(
                        demand_inventory,
                        allocations,
                    )

                    noise = self.rng.uniform(
                        0.90,
                        1.10,
                        len(active_ids),
                    )

                    on_hand = np.rint(
                        base_inventory
                        * noise
                    ).astype(
                        np.int64
                    )

                    on_hand = np.maximum(
                        on_hand,
                        0,
                    )

                    total_on_hand = int(
                        on_hand.sum()
                    )

                    if (
                        total_on_hand
                        > maximum_allowed
                    ):
                        scale = (
                            maximum_allowed
                            / total_on_hand
                        )

                        on_hand = np.floor(
                            on_hand * scale
                        ).astype(
                            np.int64
                        )

                    total_on_hand = int(
                        on_hand.sum()
                    )

                    if (
                        total_on_hand
                        > maximum_allowed
                    ):
                        excess = (
                            total_on_hand
                            - maximum_allowed
                        )

                        positive_indices = (
                            np.flatnonzero(
                                on_hand > 0
                            )
                        )

                        for index in (
                            positive_indices[::-1]
                        ):
                            if excess <= 0:
                                break

                            reduction = min(
                                int(
                                    on_hand[index]
                                ),
                                excess,
                            )

                            on_hand[index] -= (
                                reduction
                            )

                            excess -= reduction

                    final_total = int(
                        on_hand.sum()
                    )

                    if final_total > maximum_allowed:
                        raise RuntimeError(
                            "Inventory capacity "
                            "constraint violated."
                        )

                    reserved_ratio = (
                        self.rng.uniform(
                            0.0,
                            0.15,
                            len(on_hand),
                        )
                    )

                    reserved = np.floor(
                        on_hand
                        * reserved_ratio
                    ).astype(
                        np.int64
                    )

                    reserved = np.minimum(
                        reserved,
                        on_hand,
                    )

                    active_frame = pd.DataFrame(
                        {
                            "snapshot_date": (
                                snapshot_date
                            ),
                            "warehouse_id": (
                                warehouse.warehouse_id
                            ),
                            "product_id": (
                                active_ids
                            ),
                            "on_hand": (
                                on_hand
                            ),
                            "reserved": (
                                reserved
                            ),
                        }
                    )

                    rows.append(
                        active_frame
                    )

                if len(inactive_ids) > 0:
                    inactive_frame = pd.DataFrame(
                        {
                            "snapshot_date": (
                                snapshot_date
                            ),
                            "warehouse_id": (
                                warehouse.warehouse_id
                            ),
                            "product_id": (
                                inactive_ids
                            ),
                            "on_hand": np.zeros(
                                len(inactive_ids),
                                dtype=np.int64,
                            ),
                            "reserved": np.zeros(
                                len(inactive_ids),
                                dtype=np.int64,
                            ),
                        }
                    )

                    rows.append(
                        inactive_frame
                    )

        if not rows:
            return pd.DataFrame(
                columns=[
                    "snapshot_date",
                    "warehouse_id",
                    "product_id",
                    "on_hand",
                    "reserved",
                ]
            )

        result = pd.concat(
            rows,
            ignore_index=True,
        )

        result["on_hand"] = (
            pd.to_numeric(
                result["on_hand"],
                errors="coerce",
            )
            .fillna(0)
            .astype(np.int64)
        )

        result["reserved"] = (
            pd.to_numeric(
                result["reserved"],
                errors="coerce",
            )
            .fillna(0)
            .astype(np.int64)
        )

        result["on_hand"] = np.maximum(
            result["on_hand"],
            0,
        )

        result["reserved"] = np.minimum(
            result["reserved"],
            result["on_hand"],
        )

        return result

    def suppliers(self, n=50):
        return pd.DataFrame(
            [
                {
                    "supplier_id": (
                        f"SUP-{i + 1:04d}"
                    ),
                    "supplier_name": (
                        f"Supplier {i + 1:04d}"
                    ),
                    "lead_time_days": round(
                        float(
                            self.rng.uniform(
                                2,
                                14,
                            )
                        ),
                        1,
                    ),
                    "lead_time_std_days": round(
                        float(
                            self.rng.uniform(
                                0.3,
                                3,
                            )
                        ),
                        1,
                    ),
                    "reliability": round(
                        float(
                            self.rng.uniform(
                                0.70,
                                0.99,
                            )
                        ),
                        3,
                    ),
                    "capacity_units": int(
                        self.rng.integers(
                            1000,
                            20000,
                        )
                    ),
                    "unit_cost": round(
                        float(
                            self.rng.uniform(
                                5,
                                500,
                            )
                        ),
                        2,
                    ),
                    "moq": int(
                        self.rng.integers(
                            10,
                            500,
                        )
                    ),
                }
                for i in range(n)
            ]
        )

    def supplier_products(
        self,
        suppliers,
        products,
    ):
        rows = []

        product_ids = (
            products["product_id"]
            .astype(str)
            .to_numpy()
        )

        for supplier in suppliers.itertuples(
            index=False
        ):
            selected = self.rng.choice(
                product_ids,
                size=min(
                    5,
                    len(product_ids),
                ),
                replace=False,
            )

            for product_id in selected:
                rows.append(
                    {
                        "supplier_id": (
                            supplier.supplier_id
                        ),
                        "product_id": (
                            product_id
                        ),
                    }
                )

        return pd.DataFrame(rows)

    def purchase_orders(
        self,
        suppliers,
        products,
        n=500,
    ):
        rows = []

        for i in range(n):
            supplier = suppliers.iloc[
                int(
                    self.rng.integers(
                        len(suppliers)
                    )
                )
            ]

            product = products.iloc[
                int(
                    self.rng.integers(
                        len(products)
                    )
                )
            ]

            quantity = max(
                int(
                    supplier["moq"]
                ),
                int(
                    self.rng.integers(
                        1,
                        1000,
                    )
                ),
            )

            rows.append(
                {
                    "po_id": (
                        f"PO-{i + 1:06d}"
                    ),
                    "supplier_id": (
                        supplier["supplier_id"]
                    ),
                    "product_id": (
                        product["product_id"]
                    ),
                    "quantity": quantity,
                    "unit_cost": (
                        supplier["unit_cost"]
                    ),
                    "status": "OPEN",
                }
            )

        return pd.DataFrame(rows)

    def transfers(
        self,
        warehouses,
        n=300,
    ):
        rows = []

        warehouse_ids = (
            warehouses[
                "warehouse_id"
            ]
            .to_numpy()
        )

        for i in range(n):
            origin, destination = (
                self.rng.choice(
                    warehouse_ids,
                    2,
                    replace=False,
                )
            )

            rows.append(
                {
                    "transfer_id": (
                        f"TR-{i + 1:06d}"
                    ),
                    "origin_warehouse_id": (
                        origin
                    ),
                    "destination_warehouse_id": (
                        destination
                    ),
                    "quantity": int(
                        self.rng.integers(
                            10,
                            1000,
                        )
                    ),
                    "status": "PLANNED",
                }
            )

        return pd.DataFrame(rows)

    def shipment_events(
        self,
        orders,
        n=None,
    ):
        statuses = [
            "ORDER_PLACED",
            "DISPATCHED",
            "PICKED_UP",
            "WAREHOUSE_RECEIVED",
            "IN_TRANSIT",
            "DESTINATION_HUB",
            "OUT_FOR_DELIVERY",
            "DELIVERED",
        ]

        order_ids = (
            orders["order_id"]
            .dropna()
            .astype(str)
            .tolist()
        )

        if not order_ids:
            return pd.DataFrame(
                columns=[
                    "event_id",
                    "order_id",
                    "event_type",
                ]
            )

        n = n or min(
            2000,
            len(order_ids),
        )

        rows = []

        for i in range(n):
            rows.append(
                {
                    "event_id": (
                        f"EV-{i + 1:07d}"
                    ),
                    "order_id": (
                        order_ids[
                            i % len(order_ids)
                        ]
                    ),
                    "event_type": statuses[
                        int(
                            self.rng.integers(
                                len(statuses)
                            )
                        )
                    ],
                }
            )

        return pd.DataFrame(rows)