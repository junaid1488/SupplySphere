from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from collections import Counter
import re

import numpy as np
import pandas as pd

from dataset_analyzer.models import (
    DatasetProfile,
    ColumnProfile,
    InferredType,
    SemanticRole,
    SchemaIntelligence,
    CapabilityDetection,
)
from dataset_analyzer.reader import DatasetReader


@dataclass(frozen=True)
class KPIResult:
    name: str
    value: Any
    source_columns: list[str]
    calculation_basis: str
    available: bool = True
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "source_columns": self.source_columns,
            "calculation_basis": self.calculation_basis,
            "available": self.available,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class KPIReport:
    dataset_id: str
    kpis: list[KPIResult]
    computed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "kpis": [k.to_dict() for k in self.kpis],
            "computed_at": self.computed_at.isoformat(),
        }


class KPIEngine:
    def __init__(
        self,
        profile: DatasetProfile,
        schema_intelligence: SchemaIntelligence | None = None,
        capability_detection: CapabilityDetection | None = None,
        reader_provider: Callable[[], DatasetReader | None] | None = None,
    ):
        self._profile = profile
        self._schema = schema_intelligence
        self._capabilities = capability_detection
        self._reader_provider = reader_provider
        self._reader = None

    def _get_reader(self) -> DatasetReader | None:
        if self._reader is None:
            if self._reader_provider:
                try:
                    self._reader = self._reader_provider()
                except Exception:
                    pass
        return self._reader

    def compute_all(self) -> KPIReport:
        kpis = []

        kpis.extend(self._compute_dataset_overview_kpis())
        kpis.extend(self._compute_numeric_kpis())
        kpis.extend(self._compute_schema_aware_kpis())

        return KPIReport(
            dataset_id=self._profile.dataset_id,
            kpis=kpis,
            computed_at=datetime.utcnow(),
        )

    def _compute_dataset_overview_kpis(self) -> list[KPIResult]:
        kpis = []

        kpis.append(KPIResult(
            name="row_count",
            value=self._profile.row_count,
            source_columns=self._profile.column_names,
            calculation_basis="Total rows in dataset (including duplicates)",
        ))

        kpis.append(KPIResult(
            name="column_count",
            value=self._profile.column_count,
            source_columns=self._profile.column_names,
            calculation_basis="Total number of columns in dataset",
        ))

        total_cells = self._profile.row_count * self._profile.column_count
        total_nulls = sum(cp.null_count for cp in self._profile.column_profiles.values())
        missing_rate = (total_nulls / total_cells * 100) if total_cells > 0 else 0.0

        kpis.append(KPIResult(
            name="missing_value_rate",
            value=round(missing_rate, 2),
            source_columns=self._profile.column_names,
            calculation_basis=f"Total null cells ({total_nulls}) / total cells ({total_cells}) * 100",
        ))

        if self._profile.duplicate_row_count >= 0:
            dup_rate = (self._profile.duplicate_row_count / self._profile.row_count * 100) if self._profile.row_count > 0 else 0.0
            kpis.append(KPIResult(
                name="duplicate_row_count",
                value=self._profile.duplicate_row_count,
                source_columns=self._profile.column_names,
                calculation_basis=f"Exact duplicate rows counted across all {self._profile.column_count} columns",
            ))
            kpis.append(KPIResult(
                name="duplicate_row_rate",
                value=round(dup_rate, 2),
                source_columns=self._profile.column_names,
                calculation_basis=f"Duplicate rows ({self._profile.duplicate_row_count}) / total rows ({self._profile.row_count}) * 100",
            ))
        else:
            kpis.append(KPIResult(
                name="duplicate_row_count",
                value=None,
                source_columns=[],
                calculation_basis="Not computed (sampled profile)",
                available=False,
                reason="Duplicate count not available for sampled profiles",
            ))
            kpis.append(KPIResult(
                name="duplicate_row_rate",
                value=None,
                source_columns=[],
                calculation_basis="Not computed (sampled profile)",
                available=False,
                reason="Duplicate count not available for sampled profiles",
            ))

        return kpis

    @staticmethod
    def _is_id_like_column(col_name: str) -> bool:
        """Check if a column name suggests it is an identifier/key/code."""
        name_lower = col_name.lower()
        id_name_patterns = ["_id", "id_", "id", "key", "code", "pk", "uuid", "guid", "_no", "no_"]
        for pattern in id_name_patterns:
            if pattern in name_lower:
                return True
        return False

    def _compute_numeric_kpis(self) -> list[KPIResult]:
        kpis = []

        for col_name in self._profile.numeric_columns:
            col_profile = self._profile.column_profiles[col_name]

            # Skip identifier-like columns: those with ID-like names
            if self._is_id_like_column(col_name):
                continue

            stats = col_profile.numeric_stats

            if not stats:
                kpis.append(KPIResult(
                    name=f"{col_name}_sum",
                    value=None,
                    source_columns=[col_name],
                    calculation_basis="No valid numeric values",
                    available=False,
                    reason="Column has no computable numeric statistics",
                ))
                continue

            kpis.append(KPIResult(
                name=f"{col_name}_sum",
                value=stats.get("sum"),
                source_columns=[col_name],
                calculation_basis=f"Sum of non-null values in {col_name} (count: {stats.get('count', 0)})",
            ))

            kpis.append(KPIResult(
                name=f"{col_name}_mean",
                value=stats.get("mean"),
                source_columns=[col_name],
                calculation_basis=f"Arithmetic mean of non-null values in {col_name} (count: {stats.get('count', 0)})",
            ))

            kpis.append(KPIResult(
                name=f"{col_name}_median",
                value=stats.get("median"),
                source_columns=[col_name],
                calculation_basis=f"Median (50th percentile) of non-null values in {col_name} (count: {stats.get('count', 0)})",
            ))

            kpis.append(KPIResult(
                name=f"{col_name}_min",
                value=stats.get("min"),
                source_columns=[col_name],
                calculation_basis=f"Minimum of non-null values in {col_name} (count: {stats.get('count', 0)})",
            ))

            kpis.append(KPIResult(
                name=f"{col_name}_max",
                value=stats.get("max"),
                source_columns=[col_name],
                calculation_basis=f"Maximum of non-null values in {col_name} (count: {stats.get('count', 0)})",
            ))

        return kpis

    def _compute_schema_aware_kpis(self) -> list[KPIResult]:
        kpis = []

        if not self._schema:
            return kpis

        role_columns = self._get_role_columns()

        sales_cols = role_columns.get(SemanticRole.PRICE_REVENUE_VALUE, [])
        if sales_cols:
            for col in sales_cols:
                col_profile = self._profile.column_profiles.get(col)
                if col_profile and col_profile.numeric_stats:
                    stats = col_profile.numeric_stats
                    col_lower = col.lower()
                    revenue_keywords = ["revenue", "sales", "total", "gross", "net"]
                    is_revenue_field = any(kw in col_lower for kw in revenue_keywords)
                    if is_revenue_field:
                        kpi_name_prefix = "sales_total"
                    else:
                        kpi_name_prefix = col + "_total"
                    kpis.append(KPIResult(
                        name=f"{kpi_name_prefix}_{col}",
                        value=stats.get("sum"),
                        source_columns=[col],
                        calculation_basis=f"Sum of {col} (semantic role: price_revenue_value), count: {stats.get('count', 0)}",
                    ))
                    kpis.append(KPIResult(
                        name=f"{kpi_name_prefix}_{col}_average",
                        value=stats.get("mean"),
                        source_columns=[col],
                        calculation_basis=f"Mean of {col} (semantic role: price_revenue_value), count: {stats.get('count', 0)}",
                    ))

        entity_cols = role_columns.get(SemanticRole.ENTITY, [])
        product_cols = role_columns.get(SemanticRole.PRODUCT_ITEM, [])
        unique_entities = set(entity_cols + product_cols)
        if unique_entities:
            for col in unique_entities:
                col_profile = self._profile.column_profiles.get(col)
                if col_profile:
                    kpis.append(KPIResult(
                        name=f"unique_entities_{col}",
                        value=col_profile.unique_count,
                        source_columns=[col],
                        calculation_basis=f"Distinct count of {col} (semantic role: entity/product_item)",
                    ))

        inventory_cols = role_columns.get(SemanticRole.INVENTORY_STOCK, [])
        if inventory_cols:
            for col in inventory_cols:
                col_profile = self._profile.column_profiles.get(col)
                if col_profile and col_profile.numeric_stats:
                    stats = col_profile.numeric_stats
                    kpis.append(KPIResult(
                        name=f"inventory_total_{col}",
                        value=stats.get("sum"),
                        source_columns=[col],
                        calculation_basis=f"Sum of {col} (semantic role: inventory_stock), count: {stats.get('count', 0)}",
                    ))
                    kpis.append(KPIResult(
                        name=f"inventory_average_{col}",
                        value=stats.get("mean"),
                        source_columns=[col],
                        calculation_basis=f"Mean of {col} (semantic role: inventory_stock), count: {stats.get('count', 0)}",
                    ))

                    non_null_count = stats.get("count", 0)
                    if non_null_count > 0:
                        zero_count = 0
                        try:
                            reader = self._get_reader()
                            if reader:
                                df = reader.read_csv_chunked(columns=[col], max_chunks=100)
                                all_vals = []
                                for chunk in df:
                                    all_vals.extend([row[col] for row in chunk["rows"]])
                                series = pd.Series(all_vals)
                                zero_count = int((series == 0).sum())
                        except Exception:
                            pass

                        zero_rate = (zero_count / non_null_count * 100) if non_null_count > 0 else 0.0
                        kpis.append(KPIResult(
                            name=f"zero_stock_count_{col}",
                            value=zero_count,
                            source_columns=[col],
                            calculation_basis=f"Count of zero values in {col} (semantic role: inventory_stock), non-null count: {non_null_count}",
                        ))
                        kpis.append(KPIResult(
                            name=f"zero_stock_rate_{col}",
                            value=round(zero_rate, 2),
                            source_columns=[col],
                            calculation_basis=f"Zero values ({zero_count}) / non-null values ({non_null_count}) * 100 in {col}",
                        ))

        date_cols = role_columns.get(SemanticRole.DATE_TIME, [])
        if date_cols:
            for col in date_cols:
                col_profile = self._profile.column_profiles.get(col)
                if col_profile and col_profile.datetime_range:
                    dr = col_profile.datetime_range
                    min_val = dr.get("min", "")
                    max_val = dr.get("max", "")
                    # Format as readable date range string
                    min_str = str(min_val)[:10] if min_val else "N/A"
                    max_str = str(max_val)[:10] if max_val else "N/A"
                    kpis.append(KPIResult(
                        name=f"date_range_{col}",
                        value=f"{min_str} to {max_str}",
                        source_columns=[col],
                        calculation_basis=f"Min/max of parsed datetime values in {col} (semantic role: date_time)",
                    ))

        geo_cols = [c for c in self._profile.geographic_candidates]
        lat_cols = role_columns.get(SemanticRole.LATITUDE, [])
        lon_cols = role_columns.get(SemanticRole.LONGITUDE, [])
        valid_coords = 0
        if lat_cols and lon_cols:
            try:
                reader = self._get_reader()
                if reader:
                    df = reader.read_csv_chunked(columns=[lat_cols[0], lon_cols[0]], max_chunks=100)
                    all_lats = []
                    all_lons = []
                    for chunk in df:
                        all_lats.extend([row[lat_cols[0]] for row in chunk["rows"]])
                        all_lons.extend([row[lon_cols[0]] for row in chunk["rows"]])
                    lat_series = pd.Series(all_lats)
                    lon_series = pd.Series(all_lons)
                    valid_lat = lat_series.between(-90, 90)
                    valid_lon = lon_series.between(-180, 180)
                    valid_coords = int((valid_lat & valid_lon).sum())
            except Exception:
                pass

            kpis.append(KPIResult(
                name="valid_geographic_coordinates",
                value=valid_coords,
                source_columns=lat_cols + lon_cols,
                calculation_basis=f"Count of rows where latitude in [-90,90] and longitude in [-180,180] (columns: {lat_cols[0]}, {lon_cols[0]})",
            ))

        origin_cols = role_columns.get(SemanticRole.ORIGIN, [])
        if origin_cols:
            for col in origin_cols:
                col_profile = self._profile.column_profiles.get(col)
                if col_profile:
                    kpis.append(KPIResult(
                        name=f"unique_origins_{col}",
                        value=col_profile.unique_count,
                        source_columns=[col],
                        calculation_basis=f"Distinct count of {col} (semantic role: origin)",
                    ))

        dest_cols = role_columns.get(SemanticRole.DESTINATION, [])
        if dest_cols:
            for col in dest_cols:
                col_profile = self._profile.column_profiles.get(col)
                if col_profile:
                    kpis.append(KPIResult(
                        name=f"unique_destinations_{col}",
                        value=col_profile.unique_count,
                        source_columns=[col],
                        calculation_basis=f"Distinct count of {col} (semantic role: destination)",
                    ))

        if origin_cols and dest_cols:
            try:
                reader = self._get_reader()
                if reader:
                    df = reader.read_csv_chunked(columns=[origin_cols[0], dest_cols[0]], max_chunks=100)
                    pairs = set()
                    for chunk in df:
                        for row in chunk["rows"]:
                            o = row.get(origin_cols[0])
                            d = row.get(dest_cols[0])
                            if o is not None and d is not None:
                                pairs.add((o, d))
                    kpis.append(KPIResult(
                        name="unique_routes",
                        value=len(pairs),
                        source_columns=[origin_cols[0], dest_cols[0]],
                        calculation_basis=f"Distinct (origin, destination) pairs from {origin_cols[0]} and {dest_cols[0]}",
                    ))
            except Exception:
                pass

        cat_cols = role_columns.get(SemanticRole.CATEGORY, [])
        if cat_cols:
            for col in cat_cols:
                col_profile = self._profile.column_profiles.get(col)
                if col_profile and col_profile.categorical_summary:
                    kpis.append(KPIResult(
                        name=f"category_count_{col}",
                        value=len(col_profile.categorical_summary),
                        source_columns=[col],
                        calculation_basis=f"Number of distinct categories in {col} (semantic role: category)",
                    ))

        return kpis

    def _get_role_columns(self) -> dict[SemanticRole, list[str]]:
        role_columns: dict[SemanticRole, list[str]] = {}
        if self._schema:
            for detection in self._schema.detected_roles:
                if detection.role not in role_columns:
                    role_columns[detection.role] = []
                role_columns[detection.role].extend(detection.source_columns)
        return role_columns


def create_kpi_engine(
    profile: DatasetProfile,
    schema_intelligence: SchemaIntelligence | None = None,
    capability_detection: CapabilityDetection | None = None,
    reader_provider: Callable[[], DatasetReader | None] | None = None,
) -> KPIEngine:
    return KPIEngine(profile, schema_intelligence, capability_detection, reader_provider)