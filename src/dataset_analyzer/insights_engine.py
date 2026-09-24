from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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
from dataset_analyzer.kpi_engine import KPIResult


@dataclass(frozen=True)
class InsightResult:
    name: str
    value: Any
    source_columns: List[str]
    calculation_basis: str
    available: bool = True
    reason: str | None = None
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "source_columns": self.source_columns,
            "calculation_basis": self.calculation_basis,
            "available": self.available,
            "reason": self.reason,
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class InsightsReport:
    dataset_id: str
    insights: List[InsightResult]
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "insights": [i.to_dict() for i in self.insights],
            "computed_at": self.computed_at.isoformat(),
        }


class InsightsEngine:
    def __init__(
        self,
        profile: DatasetProfile,
        schema_intelligence: SchemaIntelligence | None = None,
        capability_detection: CapabilityDetection | None = None,
        reader_provider: Optional[callable] | None = None,
    ):
        self._profile = profile
        self._schema = schema_intelligence
        self._capabilities = capability_detection
        self._reader_provider = reader_provider
        self._reader = None

    def _get_reader(self) -> Optional[object]:
        if self._reader is None:
            if self._reader_provider:
                try:
                    self._reader = self._reader_provider()
                except Exception:
                    pass
        return self._reader

    def _get_role_columns(self, role: SemanticRole) -> List[str]:
        if not self._schema:
            return []
        role_cols: List[str] = []
        for detection in self._schema.detected_roles:
            if detection.role == role:
                role_cols.extend(detection.source_columns)
        return role_cols

    def compute_all(self) -> InsightsReport:
        results: List[InsightResult] = []

        # 1. Stockout risk insights
        inventory_cols = self._get_role_columns(SemanticRole.INVENTORY_STOCK)
        available_inventory = [c for c in inventory_cols if c in self._profile.column_profiles]
        if available_inventory:
            for col in available_inventory[:3]:
                cp = self._profile.column_profiles[col]
                stats = cp.numeric_stats
                if stats and "count" in stats and "mean" in stats:
                    non_null_count = stats["count"]
                    mean_val = stats["mean"]
                    zero_count = 0
                    reader = self._get_reader()
                    if reader:
                        try:
                            df_chunks = reader.read_csv_chunked(columns=[col], max_chunks=100)
                            all_vals = []
                            for chunk in df_chunks:
                                all_vals.extend([row[col] for row in chunk["rows"]])
                            series = pd.Series(all_vals)
                            zero_count = int((series == 0).sum())
                        except Exception:
                            pass
                    zero_rate = (zero_count / non_null_count * 100) if non_null_count > 0 else 0.0
                    risk_level = "high" if zero_rate > 30 else ("medium" if zero_rate > 10 else "low")
                    results.append(InsightResult(
                        name="stockout_risk",
                        value=risk_level,
                        source_columns=[col],
                        calculation_basis=f"Zero-stock rate: {zero_rate:.1f}% ({zero_count} of {non_null_count} non-null values) in {col}",
                        limitations=["Zero-stock rate based on sampled data; actual risk may vary"],
                    ))
                    break

        # 2. Supplier performance insights
        supplier_cols = self._get_role_columns(SemanticRole.SUPPLIER)
        available_supplier = [c for c in supplier_cols if c in self._profile.column_profiles]
        if available_supplier:
            for col in available_supplier[:1]:
                cp = self._profile.column_profiles[col]
                supplier_count = cp.unique_count
                results.append(InsightResult(
                    name="supplier_diversity",
                    value=supplier_count,
                    source_columns=[col],
                    calculation_basis=f"Distinct supplier count: {supplier_count} unique values in {col}",
                    limitations=["Based on distinct values detected in supplier column"],
                ))

        # 3. Category distribution insights
        cat_cols = self._get_role_columns(SemanticRole.CATEGORY)
        available_cats = [c for c in cat_cols if c in self._profile.column_profiles]
        if available_cats:
            for col in available_cats[:1]:
                cp = self._profile.column_profiles[col]
                if cp.categorical_summary:
                    total = sum(cp.categorical_summary.values())
                    top_cat = max(cp.categorical_summary.items(), key=lambda x: x[1])
                    results.append(InsightResult(
                        name="category_concentration",
                        value=top_cat[0],
                        source_columns=[col],
                        calculation_basis=f"Top category: {top_cat[0]} ({top_cat[1]} of {total} {col} entries)",
                        limitations=["Top category may not represent dominant trend in all contexts"],
                    ))

        # 4. Duplicate/quality insights
        if self._profile.duplicate_row_count >= 0 and self._profile.row_count > 0:
            dup_rate = (self._profile.duplicate_row_count / self._profile.row_count * 100) if self._profile.row_count > 0 else 0.0
            results.append(InsightResult(
                name="data_quality_duplicate_rate",
                value=round(dup_rate, 2),
                source_columns=self._profile.column_names,
                calculation_basis=f"Duplicate row rate: {round(dup_rate, 2)}% ({self._profile.duplicate_row_count} of {self._profile.row_count} rows)",
                limitations=["Duplicate count may be approximate for sampled profiles"],
            ))

        # 5. Missing value insights
        total_cells = self._profile.row_count * self._profile.column_count
        total_nulls = sum(cp.null_count for cp in self._profile.column_profiles.values())
        missing_rate = (total_nulls / total_cells * 100) if total_cells > 0 else 0.0
        if total_nulls > 0:
            results.append(InsightResult(
                name="data_missingness",
                value=round(missing_rate, 2),
                source_columns=self._profile.column_names,
                calculation_basis=f"Overall missing value rate: {round(missing_rate, 2)}% ({total_nulls} of {total_cells} cells)",
                limitations=["Missing rate across all columns; individual column rates may vary significantly"],
            ))

        # 6. Numeric column variance insights
        numeric_cols = self._profile.numeric_columns
        for col in numeric_cols[:3]:
            cp = self._profile.column_profiles.get(col)
            if cp and cp.numeric_stats:
                stats = cp.numeric_stats
                if "std" in stats and stats["count"] and stats["count"] > 2:
                    cv = (stats["std"] / abs(stats.get("mean", 1)) * 100) if stats.get("mean") else 0
                    results.append(InsightResult(
                        name="numeric_variance",
                        value=round(cv, 2),
                        source_columns=[col],
                        calculation_basis=f"Coefficient of variation: {round(cv, 2)}% in {col} (mean: {stats.get('mean', 0):.2f}, std: {stats.get('std', 0):.2f})",
                        limitations=["CV may be misleading for skewed distributions or zero-mean data"],
                    ))
                    break

        return InsightsReport(
            dataset_id=self._profile.dataset_id,
            insights=results,
            computed_at=datetime.utcnow(),
        )


def create_insights_engine(
    profile: DatasetProfile,
    schema_intelligence: SchemaIntelligence | None = None,
    capability_detection: CapabilityDetection | None = None,
    reader_provider: Optional[callable] | None = None,
) -> InsightsEngine:
    return InsightsEngine(profile, schema_intelligence, capability_detection, reader_provider)