from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from ortools.linear_solver import pywraplp

    ORTOOLS_AVAILABLE = True
except ImportError:
    pywraplp = None
    ORTOOLS_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SUPPLIER_PRODUCTS_PATH = PROCESSED_DIR / "supplier_products.csv"


@dataclass
class OptimizationResult:
    solver: str
    status: str
    optimized_cost: float
    current_cost: float
    savings: float
    service_level: float
    stockout_risk: float
    supplier_quantities: pd.DataFrame
    warehouse_quantities: pd.DataFrame
    transfers: pd.DataFrame


class SupplyOptimizer:
    def __init__(
        self,
        time_limit_ms: int = 15000,
        max_products: int = 2500,
        max_transfer_pairs_per_product: int = 36,
    ) -> None:
        self.time_limit_ms = int(time_limit_ms)
        self.max_products = int(max_products)
        self.max_transfer_pairs_per_product = int(
            max_transfer_pairs_per_product
        )

    def solve(
        self,
        suppliers: pd.DataFrame,
        warehouses: pd.DataFrame,
        demand: pd.DataFrame,
        current_inventory: pd.DataFrame,
        transport_cost_per_unit: float = 2.0,
        holding_cost_per_unit: float = 0.5,
        stockout_penalty: float = 25.0,
    ) -> OptimizationResult:
        suppliers = self._clean_suppliers(suppliers)
        warehouses = self._clean_warehouses(warehouses)
        demand = self._clean_demand(demand)
        current_inventory = self._clean_inventory(current_inventory)

        if suppliers.empty:
            return self._empty_result(
                "greedy_fallback",
                "NO_SUPPLIERS",
            )

        if warehouses.empty:
            return self._empty_result(
                "greedy_fallback",
                "NO_WAREHOUSES",
            )

        current_inventory = self._latest_inventory(
            current_inventory
        )

        if demand.empty:
            return self._result_without_demand(
                warehouses,
                current_inventory,
                holding_cost_per_unit,
            )

        demand_table = self._prepare_demand(demand)

        if demand_table.empty:
            return self._result_without_demand(
                warehouses,
                current_inventory,
                holding_cost_per_unit,
            )

        demand_table = self._limit_products(
            demand_table,
            current_inventory,
        )

        if demand_table.empty:
            return self._result_without_demand(
                warehouses,
                current_inventory,
                holding_cost_per_unit,
            )

        warehouse_state = self._build_warehouse_state(
            warehouses,
            current_inventory,
        )

        supplier_products = self._load_supplier_products(
            suppliers,
            demand_table,
        )

        current_detail = self._build_current_detail(
            demand_table,
            current_inventory,
        )

        if current_detail.empty:
            return self._result_without_demand(
                warehouses,
                current_inventory,
                holding_cost_per_unit,
            )

        transfer_candidates = self._build_transfer_candidates(
            current_detail
        )

        procurement_candidates = self._build_procurement_candidates(
            current_detail,
            suppliers,
            supplier_products,
        )

        baseline_cost = self._baseline_cost(
            warehouse_state,
            current_detail,
            holding_cost_per_unit,
            stockout_penalty,
        )

        if ORTOOLS_AVAILABLE:
            try:
                result = self._solve_ortools(
                    suppliers=suppliers,
                    warehouses=warehouses,
                    current_detail=current_detail,
                    warehouse_state=warehouse_state,
                    procurement_candidates=procurement_candidates,
                    transfer_candidates=transfer_candidates,
                    transport_cost_per_unit=transport_cost_per_unit,
                    holding_cost_per_unit=holding_cost_per_unit,
                    stockout_penalty=stockout_penalty,
                    baseline_cost=baseline_cost,
                )

                if result is not None:
                    return result
            except Exception:
                pass

        return self._solve_greedy(
            suppliers=suppliers,
            warehouses=warehouses,
            current_detail=current_detail,
            warehouse_state=warehouse_state,
            procurement_candidates=procurement_candidates,
            transfer_candidates=transfer_candidates,
            transport_cost_per_unit=transport_cost_per_unit,
            holding_cost_per_unit=holding_cost_per_unit,
            stockout_penalty=stockout_penalty,
            baseline_cost=baseline_cost,
        )

    @staticmethod
    def _clean_suppliers(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        required = [
            "supplier_id",
            "lead_time_days",
            "reliability",
            "capacity_units",
            "unit_cost",
            "moq",
        ]

        for column in required:
            if column not in out.columns:
                if column == "supplier_id":
                    raise ValueError(
                        "suppliers must contain supplier_id"
                    )
                out[column] = 0.0

        out["supplier_id"] = (
            out["supplier_id"]
            .astype(str)
            .str.strip()
        )

        numeric_columns = [
            "lead_time_days",
            "reliability",
            "capacity_units",
            "unit_cost",
            "moq",
        ]

        for column in numeric_columns:
            out[column] = pd.to_numeric(
                out[column],
                errors="coerce",
            ).fillna(0.0)

        out["reliability"] = out[
            "reliability"
        ].clip(0.0, 1.0)

        out["capacity_units"] = out[
            "capacity_units"
        ].clip(lower=0.0)

        out["unit_cost"] = out[
            "unit_cost"
        ].clip(lower=0.0)

        out["moq"] = out[
            "moq"
        ].clip(lower=0.0)

        return (
            out.drop_duplicates("supplier_id")
            .reset_index(drop=True)
        )

    @staticmethod
    def _clean_warehouses(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        if "warehouse_id" not in out.columns:
            raise ValueError(
                "warehouses must contain warehouse_id"
            )

        defaults = {
            "capacity_units": 0.0,
            "operating_cost_per_unit": 0.0,
            "latitude": 0.0,
            "longitude": 0.0,
        }

        for column, default in defaults.items():
            if column not in out.columns:
                out[column] = default

        out["warehouse_id"] = (
            out["warehouse_id"]
            .astype(str)
            .str.strip()
        )

        for column in [
            "capacity_units",
            "operating_cost_per_unit",
            "latitude",
            "longitude",
        ]:
            out[column] = pd.to_numeric(
                out[column],
                errors="coerce",
            ).fillna(0.0)

        out["capacity_units"] = out[
            "capacity_units"
        ].clip(lower=0.0)

        out["operating_cost_per_unit"] = out[
            "operating_cost_per_unit"
        ].clip(lower=0.0)

        return (
            out.drop_duplicates("warehouse_id")
            .reset_index(drop=True)
        )

    @staticmethod
    def _clean_demand(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        if "product_id" not in out.columns:
            raise ValueError(
                "demand must contain product_id"
            )

        if "forecast_7d" in out.columns:
            demand_column = "forecast_7d"
        elif "demand_7d" in out.columns:
            demand_column = "demand_7d"
        elif "demand" in out.columns:
            demand_column = "demand"
        else:
            raise ValueError(
                "demand must contain forecast_7d, "
                "demand_7d, or demand"
            )

        if "warehouse_id" not in out.columns:
            out["warehouse_id"] = ""

        out["product_id"] = (
            out["product_id"]
            .astype(str)
            .str.strip()
        )

        out["warehouse_id"] = (
            out["warehouse_id"]
            .astype(str)
            .str.strip()
        )

        out[demand_column] = pd.to_numeric(
            out[demand_column],
            errors="coerce",
        ).fillna(0.0)

        out[demand_column] = out[
            demand_column
        ].clip(lower=0.0)

        if demand_column != "forecast_7d":
            out = out.rename(
                columns={
                    demand_column: "forecast_7d"
                }
            )

        return out

    @staticmethod
    def _clean_inventory(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        required = [
            "warehouse_id",
            "product_id",
            "on_hand",
            "reserved",
        ]

        for column in required:
            if column not in out.columns:
                if column in {
                    "warehouse_id",
                    "product_id",
                }:
                    raise ValueError(
                        "current_inventory must contain "
                        f"{column}"
                    )
                out[column] = 0.0

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

        for column in [
            "on_hand",
            "reserved",
        ]:
            out[column] = pd.to_numeric(
                out[column],
                errors="coerce",
            ).fillna(0.0)

            out[column] = out[
                column
            ].clip(lower=0.0)

        if "snapshot_date" in out.columns:
            out["snapshot_date"] = pd.to_datetime(
                out["snapshot_date"],
                errors="coerce",
            )

        return out

    @staticmethod
    def _latest_inventory(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        out = df.copy()

        if "snapshot_date" in out.columns:
            valid_dates = out[
                "snapshot_date"
            ].dropna()

            if not valid_dates.empty:
                latest_date = valid_dates.max()

                out = out[
                    out["snapshot_date"] == latest_date
                ].copy()

        out["available_inventory"] = (
            out["on_hand"]
            - out["reserved"]
        ).clip(lower=0.0)

        return (
            out.groupby(
                [
                    "warehouse_id",
                    "product_id",
                ],
                as_index=False,
            )[
                [
                    "on_hand",
                    "reserved",
                    "available_inventory",
                ]
            ]
            .sum()
        )

    @staticmethod
    def _prepare_demand(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        out = df.copy()

        if "product_id" not in out.columns:
            return pd.DataFrame(
                columns=[
                    "product_id",
                    "forecast_7d",
                ]
            )

        if "forecast_7d" not in out.columns:
            return pd.DataFrame(
                columns=[
                    "product_id",
                    "forecast_7d",
                ]
            )

        if "warehouse_id" not in out.columns:
            out["warehouse_id"] = ""

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

        out["forecast_7d"] = pd.to_numeric(
            out["forecast_7d"],
            errors="coerce",
        ).fillna(0.0)

        out["forecast_7d"] = out[
            "forecast_7d"
        ].clip(lower=0.0)

        warehouse_values = out[
            "warehouse_id"
        ]

        has_real_warehouse = (
            warehouse_values.ne("")
            & warehouse_values.ne("nan")
            & warehouse_values.notna()
        ).any()

        if has_real_warehouse:
            prepared = (
                out.groupby(
                    [
                        "warehouse_id",
                        "product_id",
                    ],
                    as_index=False,
                )["forecast_7d"]
                .sum()
            )
        else:
            prepared = (
                out.groupby(
                    "product_id",
                    as_index=False,
                )["forecast_7d"]
                .sum()
            )

            prepared["warehouse_id"] = ""

        prepared["forecast_7d"] = prepared[
            "forecast_7d"
        ].clip(lower=0.0)

        return prepared[
            prepared["forecast_7d"] > 0
        ].reset_index(drop=True)

    def _limit_products(
        self,
        demand: pd.DataFrame,
        inventory: pd.DataFrame,
    ) -> pd.DataFrame:
        totals = (
            demand.groupby(
                "product_id"
            )["forecast_7d"]
            .sum()
            .sort_values(
                ascending=False
            )
        )

        if len(totals) <= self.max_products:
            return demand

        selected = set(
            totals.head(
                self.max_products
            ).index.astype(str)
        )

        return demand[
            demand["product_id"]
            .astype(str)
            .isin(selected)
        ].copy()

    def _load_supplier_products(
        self,
        suppliers: pd.DataFrame,
        demand: pd.DataFrame,
    ) -> pd.DataFrame:
        if not SUPPLIER_PRODUCTS_PATH.exists():
            return pd.DataFrame(
                columns=[
                    "supplier_id",
                    "product_id",
                ]
            )

        try:
            mapping = pd.read_csv(
                SUPPLIER_PRODUCTS_PATH
            )
        except Exception:
            return pd.DataFrame(
                columns=[
                    "supplier_id",
                    "product_id",
                ]
            )

        required = {
            "supplier_id",
            "product_id",
        }

        if not required.issubset(
            mapping.columns
        ):
            return pd.DataFrame(
                columns=[
                    "supplier_id",
                    "product_id",
                ]
            )

        mapping = mapping[
            [
                "supplier_id",
                "product_id",
            ]
        ].copy()

        mapping["supplier_id"] = (
            mapping["supplier_id"]
            .astype(str)
            .str.strip()
        )

        mapping["product_id"] = (
            mapping["product_id"]
            .astype(str)
            .str.strip()
        )

        supplier_ids = set(
            suppliers[
                "supplier_id"
            ].astype(str)
        )

        product_ids = set(
            demand[
                "product_id"
            ].astype(str)
        )

        mapping = mapping[
            mapping["supplier_id"].isin(
                supplier_ids
            )
            & mapping["product_id"].isin(
                product_ids
            )
        ]

        return (
            mapping
            .drop_duplicates()
            .reset_index(drop=True)
        )

    @staticmethod
    def _build_warehouse_state(
        warehouses: pd.DataFrame,
        inventory: pd.DataFrame,
    ) -> pd.DataFrame:
        inventory_totals = (
            inventory.groupby(
                "warehouse_id"
            )["available_inventory"]
            .sum()
            .rename("current_inventory")
        )

        state = warehouses[
            [
                "warehouse_id",
                "capacity_units",
                "operating_cost_per_unit",
            ]
        ].copy()

        state = state.merge(
            inventory_totals,
            left_on="warehouse_id",
            right_index=True,
            how="left",
        )

        state["current_inventory"] = (
            state["current_inventory"]
            .fillna(0.0)
        )

        state["preexisting_capacity_excess"] = (
            state["current_inventory"]
            - state["capacity_units"]
        ).clip(lower=0.0)

        state["free_capacity"] = (
            state["capacity_units"]
            - state["current_inventory"]
        ).clip(lower=0.0)

        state["allowed_final_inventory"] = (
            state["capacity_units"]
            + state["preexisting_capacity_excess"]
        )

        return state

    @staticmethod
    def _build_current_detail(
        demand: pd.DataFrame,
        inventory: pd.DataFrame,
    ) -> pd.DataFrame:
        columns = [
            "warehouse_id",
            "product_id",
            "forecast_7d",
            "current_inventory",
        ]

        if demand.empty:
            return pd.DataFrame(
                columns=columns
            )

        demand = demand.copy()
        inventory = inventory.copy()

        if "warehouse_id" not in demand.columns:
            demand["warehouse_id"] = ""

        demand["warehouse_id"] = (
            demand["warehouse_id"]
            .astype(str)
            .str.strip()
        )

        demand["product_id"] = (
            demand["product_id"]
            .astype(str)
            .str.strip()
        )

        warehouse_values = demand[
            "warehouse_id"
        ]

        has_real_warehouse = (
            warehouse_values.ne("")
            & warehouse_values.ne("nan")
        ).any()

        if not has_real_warehouse:
            warehouses = sorted(
                inventory[
                    "warehouse_id"
                ]
                .astype(str)
                .str.strip()
                .unique()
            )

            warehouses = [
                warehouse_id
                for warehouse_id in warehouses
                if warehouse_id
                and warehouse_id != "nan"
            ]

            if not warehouses:
                return pd.DataFrame(
                    columns=columns
                )

            product_demand = (
                demand.groupby(
                    "product_id",
                    as_index=False,
                )["forecast_7d"]
                .sum()
            )

            inventory_lookup = (
                inventory.set_index(
                    [
                        "warehouse_id",
                        "product_id",
                    ]
                )["available_inventory"]
            )

            rows: list[dict[str, Any]] = []

            warehouse_count = len(warehouses)

            for row in product_demand.itertuples(
                index=False
            ):
                product_id = str(
                    row.product_id
                )

                total_forecast = max(
                    0.0,
                    float(row.forecast_7d),
                )

                warehouse_forecast = (
                    total_forecast
                    / warehouse_count
                )

                for warehouse_id in warehouses:
                    current = float(
                        inventory_lookup.get(
                            (
                                warehouse_id,
                                product_id,
                            ),
                            0.0,
                        )
                    )

                    rows.append(
                        {
                            "warehouse_id": warehouse_id,
                            "product_id": product_id,
                            "forecast_7d": warehouse_forecast,
                            "current_inventory": max(
                                0.0,
                                current,
                            ),
                        }
                    )

            return pd.DataFrame(
                rows,
                columns=columns,
            )

        detail = demand[
            [
                "warehouse_id",
                "product_id",
                "forecast_7d",
            ]
        ].copy()

        inventory_subset = inventory[
            [
                "warehouse_id",
                "product_id",
                "available_inventory",
            ]
        ].copy()

        detail = detail.merge(
            inventory_subset,
            on=[
                "warehouse_id",
                "product_id",
            ],
            how="left",
        )

        detail = detail.rename(
            columns={
                "available_inventory":
                    "current_inventory"
            }
        )

        detail["current_inventory"] = (
            pd.to_numeric(
                detail["current_inventory"],
                errors="coerce",
            )
            .fillna(0.0)
            .clip(lower=0.0)
        )

        detail["forecast_7d"] = (
            pd.to_numeric(
                detail["forecast_7d"],
                errors="coerce",
            )
            .fillna(0.0)
            .clip(lower=0.0)
        )

        return detail[
            columns
        ].reset_index(drop=True)

    def _build_transfer_candidates(
        self,
        detail: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []

        if detail.empty:
            return candidates

        for product_id, group in detail.groupby(
            "product_id"
        ):
            group = group.copy()

            group["surplus"] = (
                group["current_inventory"]
                - group["forecast_7d"]
            ).clip(lower=0.0)

            group["shortage"] = (
                group["forecast_7d"]
                - group["current_inventory"]
            ).clip(lower=0.0)

            sources = group[
                group["surplus"] > 0
            ].sort_values(
                "surplus",
                ascending=False,
            )

            destinations = group[
                group["shortage"] > 0
            ].sort_values(
                "shortage",
                ascending=False,
            )

            if (
                sources.empty
                or destinations.empty
            ):
                continue

            pair_count = 0

            for source in sources.itertuples(
                index=False
            ):
                for destination in destinations.itertuples(
                    index=False
                ):
                    if (
                        source.warehouse_id
                        == destination.warehouse_id
                    ):
                        continue

                    max_quantity = min(
                        float(source.surplus),
                        float(destination.shortage),
                    )

                    if max_quantity <= 0:
                        continue

                    candidates.append(
                        {
                            "product_id": str(
                                product_id
                            ),
                            "origin": str(
                                source.warehouse_id
                            ),
                            "destination": str(
                                destination.warehouse_id
                            ),
                            "max_quantity": max_quantity,
                        }
                    )

                    pair_count += 1

                    if (
                        pair_count
                        >= self.max_transfer_pairs_per_product
                    ):
                        break

                if (
                    pair_count
                    >= self.max_transfer_pairs_per_product
                ):
                    break

        return candidates

    @staticmethod
    def _build_procurement_candidates(
        detail: pd.DataFrame,
        suppliers: pd.DataFrame,
        supplier_products: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        if supplier_products.empty:
            return []

        shortage_detail = detail.copy()

        shortage_detail["shortage"] = (
            shortage_detail["forecast_7d"]
            - shortage_detail["current_inventory"]
        ).clip(lower=0.0)

        shortage_detail = shortage_detail[
            shortage_detail["shortage"] > 0
        ].copy()

        if shortage_detail.empty:
            return []

        supplier_lookup = suppliers.set_index(
            "supplier_id"
        )

        mapping_by_product = (
            supplier_products.groupby(
                "product_id"
            )
        )

        candidates: list[dict[str, Any]] = []

        for row in shortage_detail.itertuples(
            index=False
        ):
            product_id = str(
                row.product_id
            )

            if (
                product_id
                not in mapping_by_product.groups
            ):
                continue

            product_mapping = (
                mapping_by_product.get_group(
                    product_id
                )
            )

            for supplier_id in (
                product_mapping[
                    "supplier_id"
                ]
            ):
                supplier_id = str(
                    supplier_id
                )

                if (
                    supplier_id
                    not in supplier_lookup.index
                ):
                    continue

                supplier = supplier_lookup.loc[
                    supplier_id
                ]

                capacity = max(
                    0.0,
                    float(
                        supplier[
                            "capacity_units"
                        ]
                    ),
                )

                moq = max(
                    0.0,
                    float(
                        supplier["moq"]
                    ),
                )

                if (
                    capacity <= 0
                    or moq > capacity
                ):
                    continue

                candidates.append(
                    {
                        "supplier_id": supplier_id,
                        "product_id": product_id,
                        "warehouse_id": str(
                            row.warehouse_id
                        ),
                        "shortage": float(
                            row.shortage
                        ),
                        "unit_cost": float(
                            supplier["unit_cost"]
                        ),
                        "moq": moq,
                        "capacity_units": capacity,
                        "reliability": float(
                            supplier["reliability"]
                        ),
                        "lead_time_days": float(
                            supplier["lead_time_days"]
                        ),
                    }
                )

        return candidates

    @staticmethod
    def _baseline_cost(
        warehouse_state: pd.DataFrame,
        detail: pd.DataFrame,
        holding_cost_per_unit: float,
        stockout_penalty: float,
    ) -> float:
        inventory_cost = float(
            (
                warehouse_state[
                    "current_inventory"
                ]
                * (
                    holding_cost_per_unit
                    + warehouse_state[
                        "operating_cost_per_unit"
                    ]
                )
            ).sum()
        )

        shortage = (
            detail["forecast_7d"]
            - detail["current_inventory"]
        ).clip(lower=0.0)

        shortage_cost = float(
            shortage.sum()
            * max(
                0.0,
                stockout_penalty,
            )
        )

        return max(
            0.0,
            inventory_cost + shortage_cost,
        )

    @staticmethod
    def _late_penalty(
        reliability: float,
        stockout_penalty: float,
    ) -> float:
        return max(
            0.0,
            stockout_penalty
            * (
                1.0
                - float(
                    np.clip(
                        reliability,
                        0.0,
                        1.0,
                    )
                )
            ),
        )

    def _solve_ortools(
        self,
        suppliers: pd.DataFrame,
        warehouses: pd.DataFrame,
        current_detail: pd.DataFrame,
        warehouse_state: pd.DataFrame,
        procurement_candidates: list[dict[str, Any]],
        transfer_candidates: list[dict[str, Any]],
        transport_cost_per_unit: float,
        holding_cost_per_unit: float,
        stockout_penalty: float,
        baseline_cost: float,
    ) -> OptimizationResult | None:
        solver = pywraplp.Solver.CreateSolver(
            "CBC"
        )

        if solver is None:
            return None

        solver.SetTimeLimit(
            self.time_limit_ms
        )

        demand_rows = list(
            current_detail.itertuples(
                index=False
            )
        )

        demand_index = {
            (
                str(row.warehouse_id),
                str(row.product_id),
            ): row
            for row in demand_rows
        }

        unmet: dict[
            tuple[str, str],
            Any,
        ] = {}

        for key, row in demand_index.items():
            forecast = max(
                0.0,
                float(row.forecast_7d),
            )

            unmet[key] = solver.NumVar(
                0.0,
                forecast,
                (
                    f"unmet_"
                    f"{self._safe_name(key[0])}_"
                    f"{self._safe_name(key[1])}"
                ),
            )

        procurement: dict[
            tuple[str, str],
            Any,
        ] = {}

        procurement_active: dict[
            tuple[str, str],
            Any,
        ] = {}

        procurement_allocations: dict[
            tuple[str, str, str],
            Any,
        ] = {}

        grouped_procurement: dict[
            tuple[str, str],
            list[dict[str, Any]],
        ] = {}

        for candidate in procurement_candidates:
            key = (
                candidate["supplier_id"],
                candidate["product_id"],
            )

            grouped_procurement.setdefault(
                key,
                [],
            ).append(candidate)

        for (
            supplier_product,
            candidates,
        ) in grouped_procurement.items():
            supplier_id, product_id = (
                supplier_product
            )

            supplier_rows = suppliers[
                suppliers["supplier_id"]
                == supplier_id
            ]

            if supplier_rows.empty:
                continue

            supplier = supplier_rows.iloc[0]

            capacity = max(
                0.0,
                float(
                    supplier["capacity_units"]
                ),
            )

            moq = max(
                0.0,
                float(
                    supplier["moq"]
                ),
            )

            if (
                capacity <= 0
                or moq > capacity
            ):
                continue

            procurement[
                supplier_product
            ] = solver.IntVar(
                0.0,
                capacity,
                (
                    f"proc_"
                    f"{self._safe_name(supplier_id)}_"
                    f"{self._safe_name(product_id)}"
                ),
            )

            procurement_active[
                supplier_product
            ] = solver.IntVar(
                0.0,
                1.0,
                (
                    f"active_"
                    f"{self._safe_name(supplier_id)}_"
                    f"{self._safe_name(product_id)}"
                ),
            )

            solver.Add(
                procurement[
                    supplier_product
                ]
                >= (
                    moq
                    * procurement_active[
                        supplier_product
                    ]
                )
            )

            solver.Add(
                procurement[
                    supplier_product
                ]
                <= (
                    capacity
                    * procurement_active[
                        supplier_product
                    ]
                )
            )

            allocation_variables = []

            for candidate in candidates:
                warehouse_id = str(
                    candidate["warehouse_id"]
                )

                shortage = max(
                    0.0,
                    float(
                        candidate["shortage"]
                    ),
                )

                allocation_key = (
                    supplier_id,
                    warehouse_id,
                    product_id,
                )

                variable = solver.NumVar(
                    0.0,
                    shortage,
                    (
                        f"alloc_"
                        f"{self._safe_name(supplier_id)}_"
                        f"{self._safe_name(warehouse_id)}_"
                        f"{self._safe_name(product_id)}"
                    ),
                )

                procurement_allocations[
                    allocation_key
                ] = variable

                allocation_variables.append(
                    variable
                )

            if allocation_variables:
                solver.Add(
                    solver.Sum(
                        allocation_variables
                    )
                    == procurement[
                        supplier_product
                    ]
                )
            else:
                solver.Add(
                    procurement[
                        supplier_product
                    ]
                    == 0
                )

        transfers: dict[
            tuple[str, str, str],
            Any,
        ] = {}

        for candidate in transfer_candidates:
            key = (
                str(candidate["origin"]),
                str(candidate["destination"]),
                str(candidate["product_id"]),
            )

            transfers[key] = solver.NumVar(
                0.0,
                max(
                    0.0,
                    float(
                        candidate["max_quantity"]
                    ),
                ),
                (
                    f"transfer_"
                    f"{self._safe_name(key[0])}_"
                    f"{self._safe_name(key[1])}_"
                    f"{self._safe_name(key[2])}"
                ),
            )

        for supplier in suppliers.itertuples(
            index=False
        ):
            supplier_id = str(
                supplier.supplier_id
            )

            variables = [
                variable
                for key, variable
                in procurement.items()
                if key[0] == supplier_id
            ]

            if variables:
                solver.Add(
                    solver.Sum(
                        variables
                    )
                    <= max(
                        0.0,
                        float(
                            supplier.capacity_units
                        ),
                    )
                )

        warehouse_lookup = (
            warehouse_state.set_index(
                "warehouse_id"
            )
        )

        for warehouse_id in (
            warehouse_state[
                "warehouse_id"
            ]
            .astype(str)
            .tolist()
        ):
            state = warehouse_lookup.loc[
                warehouse_id
            ]

            baseline_inventory = float(
                state["current_inventory"]
            )

            allowed_final_inventory = float(
                state[
                    "allowed_final_inventory"
                ]
            )

            inbound_procurement = [
                variable
                for (
                    supplier_id,
                    destination,
                    product_id,
                ), variable
                in procurement_allocations.items()
                if destination == warehouse_id
            ]

            inbound_transfers = [
                variable
                for (
                    origin,
                    destination,
                    product_id,
                ), variable
                in transfers.items()
                if destination == warehouse_id
            ]

            outbound_transfers = [
                variable
                for (
                    origin,
                    destination,
                    product_id,
                ), variable
                in transfers.items()
                if origin == warehouse_id
            ]

            inbound_procurement_total = (
                solver.Sum(
                    inbound_procurement
                )
                if inbound_procurement
                else 0.0
            )

            inbound_transfer_total = (
                solver.Sum(
                    inbound_transfers
                )
                if inbound_transfers
                else 0.0
            )

            outbound_transfer_total = (
                solver.Sum(
                    outbound_transfers
                )
                if outbound_transfers
                else 0.0
            )

            solver.Add(
                baseline_inventory
                + inbound_procurement_total
                + inbound_transfer_total
                - outbound_transfer_total
                <= allowed_final_inventory
            )

        for key, row in demand_index.items():
            warehouse_id, product_id = key

            current = max(
                0.0,
                float(row.current_inventory),
            )

            forecast = max(
                0.0,
                float(row.forecast_7d),
            )

            inbound_procurement = [
                variable
                for (
                    supplier_id,
                    destination,
                    candidate_product,
                ), variable
                in procurement_allocations.items()
                if (
                    destination == warehouse_id
                    and candidate_product == product_id
                )
            ]

            inbound_transfers = [
                variable
                for (
                    origin,
                    destination,
                    candidate_product,
                ), variable
                in transfers.items()
                if (
                    destination == warehouse_id
                    and candidate_product == product_id
                )
            ]

            outbound_transfers = [
                variable
                for (
                    origin,
                    destination,
                    candidate_product,
                ), variable
                in transfers.items()
                if (
                    origin == warehouse_id
                    and candidate_product == product_id
                )
            ]

            procurement_total = (
                solver.Sum(
                    inbound_procurement
                )
                if inbound_procurement
                else 0.0
            )

            inbound_transfer_total = (
                solver.Sum(
                    inbound_transfers
                )
                if inbound_transfers
                else 0.0
            )

            outbound_transfer_total = (
                solver.Sum(
                    outbound_transfers
                )
                if outbound_transfers
                else 0.0
            )

            solver.Add(
                current
                + procurement_total
                + inbound_transfer_total
                - outbound_transfer_total
                + unmet[key]
                >= forecast
            )

        objective = solver.Objective()

        supplier_lookup = suppliers.set_index(
            "supplier_id"
        )

        warehouse_lookup = warehouse_state.set_index(
            "warehouse_id"
        )

        for (
            supplier_id,
            warehouse_id,
            product_id,
        ), variable in procurement_allocations.items():
            supplier = supplier_lookup.loc[
                supplier_id
            ]

            warehouse = warehouse_lookup.loc[
                warehouse_id
            ]

            unit_cost = float(
                supplier["unit_cost"]
            )

            reliability = float(
                supplier["reliability"]
            )

            reliability_penalty = (
                self._late_penalty(
                    reliability,
                    stockout_penalty,
                )
            )

            operating_cost = float(
                warehouse[
                    "operating_cost_per_unit"
                ]
            )

            total_cost = (
                unit_cost
                + transport_cost_per_unit
                + holding_cost_per_unit
                + operating_cost
                + reliability_penalty
            )

            objective.SetCoefficient(
                variable,
                total_cost,
            )

        for variable in transfers.values():
            objective.SetCoefficient(
                variable,
                max(
                    0.0,
                    transport_cost_per_unit,
                ),
            )

        for variable in unmet.values():
            objective.SetCoefficient(
                variable,
                max(
                    0.0,
                    stockout_penalty,
                ),
            )

        objective.SetMinimization()

        status = solver.Solve()

        if status not in (
            pywraplp.Solver.OPTIMAL,
            pywraplp.Solver.FEASIBLE,
        ):
            return None

        supplier_rows: list[
            dict[str, Any]
        ] = []

        for key, variable in procurement.items():
            quantity = max(
                0.0,
                float(
                    variable.solution_value()
                ),
            )

            if quantity <= 1e-9:
                continue

            supplier_id, product_id = key

            supplier = supplier_lookup.loc[
                supplier_id
            ]

            reliability = float(
                supplier["reliability"]
            )

            supplier_rows.append(
                {
                    "supplier_id": supplier_id,
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_cost": float(
                        supplier["unit_cost"]
                    ),
                    "moq": float(
                        supplier["moq"]
                    ),
                    "capacity_units": float(
                        supplier["capacity_units"]
                    ),
                    "reliability": reliability,
                    "lead_time_days": float(
                        supplier["lead_time_days"]
                    ),
                    "risk_adjusted_unit_cost": (
                        float(
                            supplier["unit_cost"]
                        )
                        + self._late_penalty(
                            reliability,
                            stockout_penalty,
                        )
                    ),
                }
            )

        transfer_rows: list[
            dict[str, Any]
        ] = []

        for key, variable in transfers.items():
            quantity = max(
                0.0,
                float(
                    variable.solution_value()
                ),
            )

            if quantity <= 1e-9:
                continue

            transfer_rows.append(
                {
                    "product_id": key[2],
                    "origin": key[0],
                    "destination": key[1],
                    "quantity": quantity,
                    "status": "PLANNED",
                }
            )

        supplier_df = pd.DataFrame(
            supplier_rows,
            columns=[
                "supplier_id",
                "product_id",
                "quantity",
                "unit_cost",
                "moq",
                "capacity_units",
                "reliability",
                "lead_time_days",
                "risk_adjusted_unit_cost",
            ],
        )

        transfer_df = pd.DataFrame(
            transfer_rows,
            columns=[
                "product_id",
                "origin",
                "destination",
                "quantity",
                "status",
            ],
        )

        warehouse_df = self._build_warehouse_output(
            warehouse_state=warehouse_state,
            current_detail=current_detail,
            procurement_allocations=procurement_allocations,
            transfers=transfers,
            unmet=unmet,
        )

        optimized_cost = (
            self._calculate_optimized_cost(
                warehouse_state=warehouse_state,
                supplier_df=supplier_df,
                transfer_df=transfer_df,
                warehouse_df=warehouse_df,
                holding_cost_per_unit=holding_cost_per_unit,
                transport_cost_per_unit=transport_cost_per_unit,
                stockout_penalty=stockout_penalty,
            )
        )

        service_level = self._service_level(
            warehouse_df
        )

        result = OptimizationResult(
            solver="OR-Tools CBC",
            status=(
                "OPTIMAL"
                if status == pywraplp.Solver.OPTIMAL
                else "FEASIBLE"
            ),
            optimized_cost=float(
                optimized_cost
            ),
            current_cost=float(
                baseline_cost
            ),
            savings=float(
                baseline_cost
                - optimized_cost
            ),
            service_level=service_level,
            stockout_risk=float(
                np.clip(
                    1.0 - service_level,
                    0.0,
                    1.0,
                )
            ),
            supplier_quantities=supplier_df,
            warehouse_quantities=warehouse_df,
            transfers=transfer_df,
        )

        if not self._validate_result(
            result,
            suppliers,
            warehouses,
        ):
            return None

        return result

    def _solve_greedy(
        self,
        suppliers: pd.DataFrame,
        warehouses: pd.DataFrame,
        current_detail: pd.DataFrame,
        warehouse_state: pd.DataFrame,
        procurement_candidates: list[dict[str, Any]],
        transfer_candidates: list[dict[str, Any]],
        transport_cost_per_unit: float,
        holding_cost_per_unit: float,
        stockout_penalty: float,
        baseline_cost: float,
    ) -> OptimizationResult:
        detail = current_detail.copy()

        detail["procurement"] = 0.0
        detail["inbound_transfer"] = 0.0
        detail["outbound_transfer"] = 0.0

        detail_index = {
            (
                str(row.warehouse_id),
                str(row.product_id),
            ): index
            for index, row in detail.iterrows()
        }

        remaining_source: dict[
            tuple[str, str],
            float,
        ] = {}

        remaining_shortage: dict[
            tuple[str, str],
            float,
        ] = {}

        for row in detail.itertuples(
            index=False
        ):
            key = (
                str(row.warehouse_id),
                str(row.product_id),
            )

            remaining_source[key] = max(
                0.0,
                float(row.current_inventory)
                - float(row.forecast_7d),
            )

            remaining_shortage[key] = max(
                0.0,
                float(row.forecast_7d)
                - float(row.current_inventory),
            )

        transfer_rows: list[
            dict[str, Any]
        ] = []

        for candidate in transfer_candidates:
            source_key = (
                str(candidate["origin"]),
                str(candidate["product_id"]),
            )

            destination_key = (
                str(candidate["destination"]),
                str(candidate["product_id"]),
            )

            quantity = min(
                float(candidate["max_quantity"]),
                remaining_source.get(
                    source_key,
                    0.0,
                ),
                remaining_shortage.get(
                    destination_key,
                    0.0,
                ),
            )

            if quantity <= 0:
                continue

            remaining_source[
                source_key
            ] -= quantity

            remaining_shortage[
                destination_key
            ] -= quantity

            source_index = detail_index.get(
                source_key
            )

            destination_index = detail_index.get(
                destination_key
            )

            if source_index is not None:
                detail.loc[
                    source_index,
                    "outbound_transfer",
                ] += quantity

            if destination_index is not None:
                detail.loc[
                    destination_index,
                    "inbound_transfer",
                ] += quantity

            transfer_rows.append(
                {
                    "product_id": candidate[
                        "product_id"
                    ],
                    "origin": candidate[
                        "origin"
                    ],
                    "destination": candidate[
                        "destination"
                    ],
                    "quantity": quantity,
                    "status": "PLANNED",
                }
            )

        supplier_lookup = suppliers.set_index(
            "supplier_id"
        )

        supplier_capacity = {
            str(row.supplier_id): max(
                0.0,
                float(row.capacity_units),
            )
            for row in suppliers.itertuples(
                index=False
            )
        }

        grouped_candidates: dict[
            tuple[str, str],
            list[dict[str, Any]],
        ] = {}

        for candidate in procurement_candidates:
            key = (
                str(candidate["warehouse_id"]),
                str(candidate["product_id"]),
            )

            grouped_candidates.setdefault(
                key,
                [],
            ).append(candidate)

        supplier_rows: list[
            dict[str, Any]
        ] = []

        for key, candidates in grouped_candidates.items():
            warehouse_id, product_id = key

            detail_index_value = detail_index.get(
                key
            )

            if detail_index_value is None:
                continue

            row = detail.loc[
                detail_index_value
            ]

            shortage = max(
                0.0,
                float(row["forecast_7d"])
                - float(row["current_inventory"])
                - float(row["inbound_transfer"]),
            )

            if shortage <= 0:
                continue

            warehouse_rows = warehouse_state[
                warehouse_state["warehouse_id"]
                == warehouse_id
            ]

            if warehouse_rows.empty:
                continue

            warehouse = warehouse_rows.iloc[0]

            current_warehouse_inventory = float(
                warehouse["current_inventory"]
            )

            existing_inbound = float(
                detail[
                    detail["warehouse_id"]
                    == warehouse_id
                ]["inbound_transfer"].sum()
            )

            existing_outbound = float(
                detail[
                    detail["warehouse_id"]
                    == warehouse_id
                ]["outbound_transfer"].sum()
            )

            free_capacity = max(
                0.0,
                float(
                    warehouse[
                        "allowed_final_inventory"
                    ]
                )
                - current_warehouse_inventory
                - existing_inbound
                + existing_outbound,
            )

            shortage = min(
                shortage,
                free_capacity,
            )

            if shortage <= 0:
                continue

            candidates = sorted(
                candidates,
                key=lambda item: (
                    item["unit_cost"]
                    + self._late_penalty(
                        item["reliability"],
                        stockout_penalty,
                    ),
                    item["lead_time_days"],
                    item["supplier_id"],
                ),
            )

            for candidate in candidates:
                supplier_id = candidate[
                    "supplier_id"
                ]

                available_capacity = supplier_capacity.get(
                    supplier_id,
                    0.0,
                )

                if available_capacity <= 0:
                    continue

                moq = max(
                    0.0,
                    float(candidate["moq"]),
                )

                if moq > available_capacity:
                    continue

                quantity = min(
                    shortage,
                    available_capacity,
                )

                if (
                    quantity < moq
                    and moq <= available_capacity
                ):
                    quantity = moq

                if quantity > shortage:
                    excess = quantity - shortage
                    remaining_capacity = max(
                        0.0,
                        free_capacity - shortage,
                    )

                    if (
                        excess
                        > remaining_capacity
                        + 1e-9
                    ):
                        continue

                detail.loc[
                    detail_index_value,
                    "procurement",
                ] += quantity

                supplier_capacity[
                    supplier_id
                ] -= quantity

                shortage = max(
                    0.0,
                    shortage - quantity,
                )

                supplier = supplier_lookup.loc[
                    supplier_id
                ]

                reliability = float(
                    supplier["reliability"]
                )

                supplier_rows.append(
                    {
                        "supplier_id": supplier_id,
                        "product_id": product_id,
                        "quantity": quantity,
                        "unit_cost": float(
                            supplier["unit_cost"]
                        ),
                        "moq": float(
                            supplier["moq"]
                        ),
                        "capacity_units": float(
                            supplier["capacity_units"]
                        ),
                        "reliability": reliability,
                        "lead_time_days": float(
                            supplier["lead_time_days"]
                        ),
                        "risk_adjusted_unit_cost": (
                            float(
                                supplier["unit_cost"]
                            )
                            + self._late_penalty(
                                reliability,
                                stockout_penalty,
                            )
                        ),
                    }
                )

                if shortage <= 0:
                    break

        detail["final_inventory"] = (
            detail["current_inventory"]
            + detail["procurement"]
            + detail["inbound_transfer"]
            - detail["outbound_transfer"]
        )

        detail["unmet_demand"] = (
            detail["forecast_7d"]
            - detail["final_inventory"]
        ).clip(lower=0.0)

        supplier_df = pd.DataFrame(
            supplier_rows,
            columns=[
                "supplier_id",
                "product_id",
                "quantity",
                "unit_cost",
                "moq",
                "capacity_units",
                "reliability",
                "lead_time_days",
                "risk_adjusted_unit_cost",
            ],
        )

        transfer_df = pd.DataFrame(
            transfer_rows,
            columns=[
                "product_id",
                "origin",
                "destination",
                "quantity",
                "status",
            ],
        )

        warehouse_df = (
            self._build_warehouse_output_from_detail(
                warehouse_state,
                detail,
            )
        )

        optimized_cost = (
            self._calculate_optimized_cost(
                warehouse_state=warehouse_state,
                supplier_df=supplier_df,
                transfer_df=transfer_df,
                warehouse_df=warehouse_df,
                holding_cost_per_unit=holding_cost_per_unit,
                transport_cost_per_unit=transport_cost_per_unit,
                stockout_penalty=stockout_penalty,
            )
        )

        service_level = self._service_level(
            warehouse_df
        )

        return OptimizationResult(
            solver="greedy_fallback",
            status="FEASIBLE",
            optimized_cost=float(
                max(
                    0.0,
                    optimized_cost,
                )
            ),
            current_cost=float(
                max(
                    0.0,
                    baseline_cost,
                )
            ),
            savings=float(
                baseline_cost
                - optimized_cost
            ),
            service_level=service_level,
            stockout_risk=float(
                np.clip(
                    1.0 - service_level,
                    0.0,
                    1.0,
                )
            ),
            supplier_quantities=supplier_df,
            warehouse_quantities=warehouse_df,
            transfers=transfer_df,
        )

    @staticmethod
    def _build_warehouse_output(
        warehouse_state: pd.DataFrame,
        current_detail: pd.DataFrame,
        procurement_allocations: dict[
            tuple[str, str, str],
            Any,
        ],
        transfers: dict[
            tuple[str, str, str],
            Any,
        ],
        unmet: dict[
            tuple[str, str],
            Any,
        ],
    ) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []

        for warehouse in warehouse_state.itertuples(
            index=False
        ):
            warehouse_id = str(
                warehouse.warehouse_id
            )

            detail_rows = current_detail[
                current_detail["warehouse_id"]
                == warehouse_id
            ]

            demand = float(
                detail_rows["forecast_7d"].sum()
            )

            current_inventory = float(
                warehouse.current_inventory
            )

            procurement = 0.0

            for (
                supplier_id,
                destination,
                product_id,
            ), variable in procurement_allocations.items():
                if destination == warehouse_id:
                    procurement += max(
                        0.0,
                        float(
                            variable.solution_value()
                        ),
                    )

            inbound = 0.0
            outbound = 0.0

            for (
                origin,
                destination,
                product_id,
            ), variable in transfers.items():
                quantity = max(
                    0.0,
                    float(
                        variable.solution_value()
                    ),
                )

                if destination == warehouse_id:
                    inbound += quantity

                if origin == warehouse_id:
                    outbound += quantity

            unmet_demand = 0.0

            for key, variable in unmet.items():
                if key[0] == warehouse_id:
                    unmet_demand += max(
                        0.0,
                        float(
                            variable.solution_value()
                        ),
                    )

            final_inventory = (
                current_inventory
                + procurement
                + inbound
                - outbound
            )

            fulfilled = max(
                0.0,
                demand - unmet_demand,
            )

            service_level = (
                fulfilled / demand
                if demand > 0
                else 1.0
            )

            rows.append(
                {
                    "warehouse_id": warehouse_id,
                    "current_inventory": current_inventory,
                    "forecast_7d": demand,
                    "procurement": procurement,
                    "inbound_transfer": inbound,
                    "outbound_transfer": outbound,
                    "final_inventory": final_inventory,
                    "unmet_demand": unmet_demand,
                    "capacity_units": float(
                        warehouse.capacity_units
                    ),
                    "allowed_final_inventory": float(
                        warehouse.allowed_final_inventory
                    ),
                    "service_level": float(
                        np.clip(
                            service_level,
                            0.0,
                            1.0,
                        )
                    ),
                    "status": "PLANNED",
                }
            )

        return pd.DataFrame(rows)

    @staticmethod
    def _build_warehouse_output_from_detail(
        warehouse_state: pd.DataFrame,
        detail: pd.DataFrame,
    ) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []

        for warehouse in warehouse_state.itertuples(
            index=False
        ):
            warehouse_id = str(
                warehouse.warehouse_id
            )

            detail_rows = detail[
                detail["warehouse_id"]
                == warehouse_id
            ]

            demand = float(
                detail_rows[
                    "forecast_7d"
                ].sum()
            )

            current_inventory = float(
                warehouse.current_inventory
            )

            procurement = float(
                detail_rows[
                    "procurement"
                ].sum()
            )

            inbound = float(
                detail_rows[
                    "inbound_transfer"
                ].sum()
            )

            outbound = float(
                detail_rows[
                    "outbound_transfer"
                ].sum()
            )

            final_inventory = (
                current_inventory
                + procurement
                + inbound
                - outbound
            )

            unmet_demand = float(
                detail_rows[
                    "unmet_demand"
                ].sum()
            )

            fulfilled = max(
                0.0,
                demand - unmet_demand,
            )

            service_level = (
                fulfilled / demand
                if demand > 0
                else 1.0
            )

            rows.append(
                {
                    "warehouse_id": warehouse_id,
                    "current_inventory": current_inventory,
                    "forecast_7d": demand,
                    "procurement": procurement,
                    "inbound_transfer": inbound,
                    "outbound_transfer": outbound,
                    "final_inventory": final_inventory,
                    "unmet_demand": unmet_demand,
                    "capacity_units": float(
                        warehouse.capacity_units
                    ),
                    "allowed_final_inventory": float(
                        warehouse.allowed_final_inventory
                    ),
                    "service_level": float(
                        np.clip(
                            service_level,
                            0.0,
                            1.0,
                        )
                    ),
                    "status": "PLANNED",
                }
            )

        return pd.DataFrame(rows)

    @staticmethod
    def _calculate_optimized_cost(
        warehouse_state: pd.DataFrame,
        supplier_df: pd.DataFrame,
        transfer_df: pd.DataFrame,
        warehouse_df: pd.DataFrame,
        holding_cost_per_unit: float,
        transport_cost_per_unit: float,
        stockout_penalty: float,
    ) -> float:
        cost = 0.0

        if not supplier_df.empty:
            procurement_cost = (
                supplier_df["quantity"]
                * supplier_df["unit_cost"]
            ).sum()

            procurement_transport = (
                supplier_df["quantity"]
                * transport_cost_per_unit
            ).sum()

            risk_penalty = (
                supplier_df["quantity"]
                * (
                    1.0
                    - supplier_df["reliability"]
                )
                * stockout_penalty
            ).sum()

            cost += float(
                procurement_cost
                + procurement_transport
                + risk_penalty
            )

        if not transfer_df.empty:
            cost += float(
                (
                    transfer_df["quantity"]
                    * transport_cost_per_unit
                ).sum()
            )

        if not warehouse_df.empty:
            warehouse_cost = warehouse_df.copy()

            warehouse_cost["final_inventory"] = pd.to_numeric(
                warehouse_cost["final_inventory"],
                errors="coerce",
            ).fillna(0.0).clip(lower=0.0)

            if "operating_cost_per_unit" in warehouse_cost.columns:
                warehouse_cost["operating_cost_per_unit"] = pd.to_numeric(
                    warehouse_cost["operating_cost_per_unit"],
                    errors="coerce",
                ).fillna(0.0).clip(lower=0.0)
            else:
                warehouse_cost = warehouse_cost.merge(
                    warehouse_state[
                        [
                            "warehouse_id",
                            "operating_cost_per_unit",
                        ]
                    ],
                    on="warehouse_id",
                    how="left",
                )

                warehouse_cost["operating_cost_per_unit"] = pd.to_numeric(
                    warehouse_cost["operating_cost_per_unit"],
                    errors="coerce",
                ).fillna(0.0).clip(lower=0.0)

            holding_cost = (
                warehouse_cost["final_inventory"]
                * holding_cost_per_unit
            ).sum()

            operating_cost = (
                warehouse_cost["final_inventory"]
                * warehouse_cost["operating_cost_per_unit"]
            ).sum()

            unmet_demand = pd.to_numeric(
                warehouse_cost["unmet_demand"],
                errors="coerce",
            ).fillna(0.0).clip(lower=0.0)

            stockout_cost = (
                unmet_demand
                * stockout_penalty
            ).sum()

            cost += float(
                holding_cost
                + operating_cost
                + stockout_cost
            )

        return max(
            0.0,
            float(cost),
        )

    @staticmethod
    def _service_level(
        warehouse_df: pd.DataFrame,
    ) -> float:
        if warehouse_df.empty:
            return 1.0

        demand = float(
            warehouse_df["forecast_7d"].sum()
        )

        unmet = float(
            warehouse_df["unmet_demand"].sum()
        )

        if demand <= 0:
            return 1.0

        return float(
            np.clip(
                (demand - unmet) / demand,
                0.0,
                1.0,
            )
        )

    @staticmethod
    def _validate_result(
        result: OptimizationResult,
        suppliers: pd.DataFrame,
        warehouses: pd.DataFrame,
    ) -> bool:
        if result.optimized_cost < 0:
            return False

        if result.current_cost < 0:
            return False

        if not 0.0 <= result.service_level <= 1.0:
            return False

        if not 0.0 <= result.stockout_risk <= 1.0:
            return False

        supplier_df = result.supplier_quantities

        if not supplier_df.empty:
            if (
                supplier_df["quantity"]
                < -1e-9
            ).any():
                return False

            capacity_lookup = (
                suppliers.set_index(
                    "supplier_id"
                )["capacity_units"]
            )

            supplier_totals = (
                supplier_df.groupby(
                    "supplier_id"
                )["quantity"]
                .sum()
            )

            for supplier_id, quantity in (
                supplier_totals.items()
            ):
                capacity = float(
                    capacity_lookup.get(
                        supplier_id,
                        0.0,
                    )
                )

                if quantity > capacity + 1e-6:
                    return False

        warehouse_df = result.warehouse_quantities

        if not warehouse_df.empty:
            warehouse_ids = set(
                warehouses[
                    "warehouse_id"
                ].astype(str)
            )

            if not set(
                warehouse_df[
                    "warehouse_id"
                ].astype(str)
            ).issubset(
                warehouse_ids
            ):
                return False

            if (
                warehouse_df[
                    "final_inventory"
                ] < -1e-9
            ).any():
                return False

            if (
                warehouse_df[
                    "unmet_demand"
                ] < -1e-9
            ).any():
                return False

            if (
                warehouse_df["final_inventory"]
                - warehouse_df[
                    "allowed_final_inventory"
                ]
                > 1e-6
            ).any():
                return False

        transfer_df = result.transfers

        if not transfer_df.empty:
            if (
                transfer_df["quantity"]
                < -1e-9
            ).any():
                return False

            if (
                transfer_df["origin"]
                == transfer_df["destination"]
            ).any():
                return False

        return True

    @staticmethod
    def _result_without_demand(
        warehouses: pd.DataFrame,
        inventory: pd.DataFrame,
        holding_cost_per_unit: float,
    ) -> OptimizationResult:
        warehouse_state = SupplyOptimizer._build_warehouse_state(
            warehouses,
            inventory,
        )

        rows = []

        for row in warehouse_state.itertuples(
            index=False
        ):
            rows.append(
                {
                    "warehouse_id": str(
                        row.warehouse_id
                    ),
                    "current_inventory": float(
                        row.current_inventory
                    ),
                    "forecast_7d": 0.0,
                    "procurement": 0.0,
                    "inbound_transfer": 0.0,
                    "outbound_transfer": 0.0,
                    "final_inventory": float(
                        row.current_inventory
                    ),
                    "unmet_demand": 0.0,
                    "capacity_units": float(
                        row.capacity_units
                    ),
                    "allowed_final_inventory": float(
                        row.allowed_final_inventory
                    ),
                    "service_level": 1.0,
                    "status": "NO_DEMAND",
                }
            )

        warehouse_df = pd.DataFrame(rows)

        current_cost = float(
            (
                warehouse_state["current_inventory"]
                * (
                    holding_cost_per_unit
                    + warehouse_state[
                        "operating_cost_per_unit"
                    ]
                )
            ).sum()
        )

        return OptimizationResult(
            solver="greedy_fallback",
            status="NO_DEMAND",
            optimized_cost=current_cost,
            current_cost=current_cost,
            savings=0.0,
            service_level=1.0,
            stockout_risk=0.0,
            supplier_quantities=pd.DataFrame(
                columns=[
                    "supplier_id",
                    "product_id",
                    "quantity",
                    "unit_cost",
                    "moq",
                    "capacity_units",
                    "reliability",
                    "lead_time_days",
                    "risk_adjusted_unit_cost",
                ]
            ),
            warehouse_quantities=warehouse_df,
            transfers=pd.DataFrame(
                columns=[
                    "product_id",
                    "origin",
                    "destination",
                    "quantity",
                    "status",
                ]
            ),
        )

    @staticmethod
    def _empty_result(
        solver: str,
        status: str,
    ) -> OptimizationResult:
        return OptimizationResult(
            solver=solver,
            status=status,
            optimized_cost=0.0,
            current_cost=0.0,
            savings=0.0,
            service_level=0.0,
            stockout_risk=1.0,
            supplier_quantities=pd.DataFrame(),
            warehouse_quantities=pd.DataFrame(),
            transfers=pd.DataFrame(),
        )

    @staticmethod
    def _safe_name(value: Any) -> str:
        text = str(value)

        cleaned = "".join(
            character
            if character.isalnum()
            else "_"
            for character in text
        )

        return cleaned[:80] or "value"