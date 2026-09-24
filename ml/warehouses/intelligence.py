from __future__ import annotations

import numpy as np
import pandas as pd


def _numeric(
    frame: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    out = frame.copy()

    for column in columns:
        if column in out.columns:
            out[column] = pd.to_numeric(
                out[column],
                errors="coerce",
            ).fillna(0.0)

    return out


def _prepare_warehouses(
    warehouses: pd.DataFrame,
) -> pd.DataFrame:
    required = {
        "warehouse_id",
        "city",
        "latitude",
        "longitude",
        "capacity_units",
        "operating_cost_per_unit",
    }

    missing = required - set(warehouses.columns)

    if missing:
        raise ValueError(
            f"Missing warehouse columns: {sorted(missing)}"
        )

    out = warehouses.copy()

    out["warehouse_id"] = (
        out["warehouse_id"]
        .astype(str)
        .str.strip()
    )

    out = _numeric(
        out,
        [
            "latitude",
            "longitude",
            "capacity_units",
            "operating_cost_per_unit",
        ],
    )

    if out["warehouse_id"].duplicated().any():
        raise ValueError(
            "Duplicate warehouse_id values detected."
        )

    if (out["capacity_units"] < 0).any():
        raise ValueError(
            "Warehouse capacity cannot be negative."
        )

    if (out["operating_cost_per_unit"] < 0).any():
        raise ValueError(
            "Operating cost per unit cannot be negative."
        )

    return out.reset_index(drop=True)


def _prepare_inventory(
    inventory: pd.DataFrame,
) -> pd.DataFrame:
    required = {
        "snapshot_date",
        "warehouse_id",
        "product_id",
        "on_hand",
        "reserved",
    }

    missing = required - set(inventory.columns)

    if missing:
        raise ValueError(
            f"Missing inventory columns: {sorted(missing)}"
        )

    out = inventory.copy()

    out["snapshot_date"] = pd.to_datetime(
        out["snapshot_date"],
        errors="coerce",
    ).dt.floor("D")

    out["warehouse_id"] = (
        out["warehouse_id"]
        .astype(str)
        .str.strip()
    )

    out["product_id"] = (
        out["product_id"]
        .astype(str)
        .str.strip()
    )

    out = _numeric(
        out,
        [
            "on_hand",
            "reserved",
        ],
    )

    out = out.dropna(
        subset=[
            "snapshot_date",
            "warehouse_id",
            "product_id",
        ]
    )

    if (out["on_hand"] < 0).any():
        raise ValueError(
            "Inventory on_hand cannot be negative."
        )

    if (out["reserved"] < 0).any():
        raise ValueError(
            "Inventory reserved cannot be negative."
        )

    if (out["reserved"] > out["on_hand"]).any():
        raise ValueError(
            "Reserved inventory cannot exceed on_hand inventory."
        )

    return out.reset_index(drop=True)


def _latest_inventory_snapshot(
    inventory: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    if inventory.empty:
        raise ValueError(
            "Inventory data cannot be empty."
        )

    latest_date = inventory["snapshot_date"].max()

    latest = inventory[
        inventory["snapshot_date"] == latest_date
    ].copy()

    if latest.empty:
        raise ValueError(
            "Latest inventory snapshot is empty."
        )

    duplicate_keys = (
        latest
        .duplicated(
            subset=[
                "warehouse_id",
                "product_id",
            ],
            keep=False,
        )
    )

    if duplicate_keys.any():
        latest = (
            latest
            .groupby(
                [
                    "warehouse_id",
                    "product_id",
                ],
                as_index=False,
            )
            .agg(
                on_hand=("on_hand", "sum"),
                reserved=("reserved", "sum"),
            )
        )
        latest["snapshot_date"] = latest_date

    return latest.reset_index(drop=True), latest_date


def _prepare_forecast(
    forecast: pd.DataFrame,
) -> pd.DataFrame:
    required = {
        "product_id",
        "forecast_7d",
    }

    missing = required - set(forecast.columns)

    if missing:
        raise ValueError(
            f"Missing forecast columns: {sorted(missing)}"
        )

    out = forecast.copy()

    out["product_id"] = (
        out["product_id"]
        .astype(str)
        .str.strip()
    )

    out["forecast_7d"] = pd.to_numeric(
        out["forecast_7d"],
        errors="coerce",
    ).fillna(0.0)

    out = (
        out
        .groupby(
            "product_id",
            as_index=False,
        )["forecast_7d"]
        .sum()
    )

    out["forecast_7d"] = out["forecast_7d"].clip(
        lower=0.0
    )

    return out


def warehouse_metrics(
    warehouses: pd.DataFrame,
    inventory: pd.DataFrame,
    demand: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Calculate current warehouse operating metrics.

    Inventory is point-in-time data. Historical snapshots are never
    summed together. Only the latest snapshot is used for current
    inventory, capacity, utilization, and operating-cost calculations.

    If explicit demand data is supplied, demand_served is derived from
    that data. Otherwise demand_served remains zero rather than being
    fabricated from inventory balances.
    """

    w = _prepare_warehouses(warehouses)
    inv = _prepare_inventory(inventory)

    latest, latest_date = _latest_inventory_snapshot(inv)

    inventory_agg = (
        latest
        .groupby(
            "warehouse_id",
            as_index=False,
        )
        .agg(
            inventory_units=("on_hand", "sum"),
            reserved_units=("reserved", "sum"),
        )
    )

    out = w.merge(
        inventory_agg,
        on="warehouse_id",
        how="left",
    )

    out[
        [
            "inventory_units",
            "reserved_units",
        ]
    ] = out[
        [
            "inventory_units",
            "reserved_units",
        ]
    ].fillna(0.0)

    out["available_inventory_units"] = (
        out["inventory_units"]
        - out["reserved_units"]
    ).clip(lower=0.0)

    out["free_capacity_units"] = (
        out["capacity_units"]
        - out["inventory_units"]
    )

    out["utilization"] = np.where(
        out["capacity_units"] > 0,
        out["inventory_units"]
        / out["capacity_units"],
        0.0,
    )

    out["inbound_volume"] = (
        out["reserved_units"]
    )

    if demand is not None and not demand.empty:
        d = demand.copy()

        if {
            "warehouse_id",
            "demand",
        }.issubset(d.columns):
            d["warehouse_id"] = (
                d["warehouse_id"]
                .astype(str)
                .str.strip()
            )

            d["demand"] = pd.to_numeric(
                d["demand"],
                errors="coerce",
            ).fillna(0.0)

            demand_agg = (
                d.groupby(
                    "warehouse_id",
                    as_index=False,
                )["demand"]
                .sum()
                .rename(
                    columns={
                        "demand": "demand_served"
                    }
                )
            )

            out = out.merge(
                demand_agg,
                on="warehouse_id",
                how="left",
            )

            out["demand_served"] = (
                out["demand_served"]
                .fillna(0.0)
                .clip(lower=0.0)
            )
        else:
            out["demand_served"] = 0.0
    else:
        out["demand_served"] = 0.0

    out["outbound_volume"] = (
        out["demand_served"]
    )

    out["operating_cost"] = (
        out["inventory_units"]
        * out["operating_cost_per_unit"]
    )

    out["snapshot_date"] = latest_date

    columns = [
        "warehouse_id",
        "city",
        "latitude",
        "longitude",
        "capacity_units",
        "operating_cost_per_unit",
        "snapshot_date",
        "inventory_units",
        "reserved_units",
        "available_inventory_units",
        "free_capacity_units",
        "utilization",
        "inbound_volume",
        "outbound_volume",
        "demand_served",
        "operating_cost",
    ]

    return (
        out[columns]
        .sort_values("warehouse_id")
        .reset_index(drop=True)
    )


def recommend_allocation(
    warehouses: pd.DataFrame,
    inventory: pd.DataFrame,
    forecast: pd.DataFrame,
    customer_centroids: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Recommend product inventory allocation across warehouses.

    Current inventory comes only from the latest inventory snapshot.

    The target for each product is its 7-day forecast. Existing inventory
    is retained wherever possible, and only the additional inventory
    required above current stock is allocated.

    Allocation respects current warehouse free capacity.

    Products that cannot be fully allocated because of genuine capacity
    constraints are returned with the allocated quantity and status
    rather than silently overfilling a warehouse.
    """

    del customer_centroids

    w = _prepare_warehouses(warehouses)
    inv = _prepare_inventory(inventory)
    f = _prepare_forecast(forecast)

    latest, _ = _latest_inventory_snapshot(inv)

    current = (
        latest
        .groupby(
            [
                "warehouse_id",
                "product_id",
            ],
            as_index=False,
        )
        .agg(
            current_inventory=("on_hand", "sum"),
            reserved_inventory=("reserved", "sum"),
        )
    )

    wm = warehouse_metrics(
        w,
        inv,
    )

    free_capacity = (
        wm.set_index("warehouse_id")
        ["free_capacity_units"]
        .clip(lower=0.0)
        .to_dict()
    )

    capacity_cost = (
        wm.set_index("warehouse_id")
        ["operating_cost_per_unit"]
        .to_dict()
    )

    warehouse_ids = (
        w["warehouse_id"]
        .astype(str)
        .tolist()
    )

    rows: list[dict] = []

    current_lookup = {
        (
            str(row.warehouse_id),
            str(row.product_id),
        ): float(row.current_inventory)
        for row in current.itertuples(index=False)
    }

    for row in f.itertuples(index=False):
        product_id = str(row.product_id)
        forecast_7d = max(
            0.0,
            float(row.forecast_7d),
        )

        if forecast_7d <= 0:
            continue

        product_current = {
            warehouse_id: current_lookup.get(
                (
                    warehouse_id,
                    product_id,
                ),
                0.0,
            )
            for warehouse_id in warehouse_ids
        }

        total_current = sum(
            product_current.values()
        )

        additional_required = max(
            0.0,
            forecast_7d - total_current,
        )

        allocation = {
            warehouse_id: 0.0
            for warehouse_id in warehouse_ids
        }

        remaining = additional_required

        while remaining > 1e-9:
            candidates = [
                warehouse_id
                for warehouse_id in warehouse_ids
                if free_capacity.get(
                    warehouse_id,
                    0.0,
                ) > 1e-9
            ]

            if not candidates:
                break

            candidates.sort(
                key=lambda warehouse_id: (
                    -free_capacity.get(
                        warehouse_id,
                        0.0,
                    ),
                    capacity_cost.get(
                        warehouse_id,
                        0.0,
                    ),
                    warehouse_id,
                )
            )

            allocated_this_round = False

            for warehouse_id in candidates:
                available_capacity = max(
                    0.0,
                    free_capacity.get(
                        warehouse_id,
                        0.0,
                    ),
                )

                if available_capacity <= 0:
                    continue

                quantity = min(
                    remaining,
                    available_capacity,
                )

                allocation[warehouse_id] += quantity

                free_capacity[warehouse_id] -= quantity
                remaining -= quantity

                allocated_this_round = True

                if remaining <= 1e-9:
                    break

            if not allocated_this_round:
                break

        for warehouse_id in warehouse_ids:
            current_inventory = product_current[
                warehouse_id
            ]

            recommended_inventory = (
                current_inventory
                + allocation[warehouse_id]
            )

            additional_inventory = allocation[
                warehouse_id
            ]

            if remaining <= 1e-9:
                status = "PLANNED"
            elif additional_required <= 1e-9:
                status = "CURRENT_STOCK_SUFFICIENT"
            else:
                status = "CAPACITY_CONSTRAINED"

            rows.append(
                {
                    "product_id": product_id,
                    "warehouse_id": warehouse_id,
                    "current_inventory": round(
                        current_inventory,
                        2,
                    ),
                    "forecast_7d": round(
                        forecast_7d,
                        2,
                    ),
                    "recommended_inventory": round(
                        recommended_inventory,
                        2,
                    ),
                    "additional_inventory": round(
                        additional_inventory,
                        2,
                    ),
                    "status": status,
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "product_id",
            "warehouse_id",
            "current_inventory",
            "forecast_7d",
            "recommended_inventory",
            "additional_inventory",
            "status",
        ],
    )


def transfer_recommendations(
    warehouses: pd.DataFrame,
    inventory: pd.DataFrame,
    forecast: pd.DataFrame,
) -> pd.DataFrame:
    """
    Recommend feasible warehouse transfers using the latest inventory
    snapshot.

    A source warehouse must have surplus above two times the product's
    7-day forecast.

    A destination must have a product shortage and positive free
    capacity.

    Source availability and destination capacity are explicitly checked.
    """

    w = _prepare_warehouses(warehouses)
    inv = _prepare_inventory(inventory)
    f = _prepare_forecast(forecast)

    latest, _ = _latest_inventory_snapshot(inv)

    current = (
        latest
        .groupby(
            [
                "warehouse_id",
                "product_id",
            ],
            as_index=False,
        )
        .agg(
            on_hand=("on_hand", "sum"),
            reserved=("reserved", "sum"),
        )
    )

    wm = warehouse_metrics(
        w,
        inv,
    )

    free_capacity = (
        wm.set_index("warehouse_id")
        ["free_capacity_units"]
        .clip(lower=0.0)
        .to_dict()
    )

    x = current.merge(
        f,
        on="product_id",
        how="left",
    )

    x["forecast_7d"] = (
        x["forecast_7d"]
        .fillna(0.0)
        .clip(lower=0.0)
    )

    x["available_inventory"] = (
        x["on_hand"]
        - x["reserved"]
    ).clip(lower=0.0)

    x["surplus"] = (
        x["available_inventory"]
        - x["forecast_7d"] * 2.0
    ).clip(lower=0.0)

    x["shortage"] = (
        x["forecast_7d"]
        - x["available_inventory"]
    ).clip(lower=0.0)

    rows: list[dict] = []

    for product_id, group in x.groupby(
        "product_id",
        sort=False,
    ):
        sources = (
            group[
                group["surplus"] > 0
            ]
            .sort_values(
                "surplus",
                ascending=False,
            )
            .copy()
        )

        destinations = (
            group[
                group["shortage"] > 0
            ]
            .sort_values(
                "shortage",
                ascending=False,
            )
            .copy()
        )

        if sources.empty or destinations.empty:
            continue

        source_remaining = {
            str(row.warehouse_id): float(
                row.surplus
            )
            for row in sources.itertuples(
                index=False
            )
        }

        destination_remaining = {
            str(row.warehouse_id): float(
                row.shortage
            )
            for row in destinations.itertuples(
                index=False
            )
        }

        for destination in destinations.itertuples(
            index=False
        ):
            destination_id = str(
                destination.warehouse_id
            )

            needed = destination_remaining[
                destination_id
            ]

            if needed <= 0:
                continue

            destination_capacity = max(
                0.0,
                free_capacity.get(
                    destination_id,
                    0.0,
                ),
            )

            if destination_capacity <= 0:
                continue

            transferable_to_destination = min(
                needed,
                destination_capacity,
            )

            for source in sources.itertuples(
                index=False
            ):
                source_id = str(
                    source.warehouse_id
                )

                if source_id == destination_id:
                    continue

                source_available = max(
                    0.0,
                    source_remaining.get(
                        source_id,
                        0.0,
                    ),
                )

                if source_available <= 0:
                    continue

                quantity = min(
                    source_available,
                    transferable_to_destination,
                )

                if quantity <= 0:
                    continue

                rows.append(
                    {
                        "product_id": str(
                            product_id
                        ),
                        "origin_warehouse_id": source_id,
                        "destination_warehouse_id": destination_id,
                        "quantity": round(
                            quantity,
                            2,
                        ),
                        "status": "PLANNED",
                    }
                )

                source_remaining[
                    source_id
                ] -= quantity

                destination_capacity -= quantity
                free_capacity[
                    destination_id
                ] -= quantity

                transferable_to_destination -= quantity
                destination_remaining[
                    destination_id
                ] -= quantity

                if (
                    transferable_to_destination
                    <= 1e-9
                ):
                    break

    return pd.DataFrame(
        rows,
        columns=[
            "product_id",
            "origin_warehouse_id",
            "destination_warehouse_id",
            "quantity",
            "status",
        ],
    )