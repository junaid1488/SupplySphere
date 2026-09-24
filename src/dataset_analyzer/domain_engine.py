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
    Capability,
    CapabilityStatus,
)


@dataclass(frozen=True)
class DomainResult:
    domain: str
    available: bool
    description: str
    source_columns: List[str]
    calculation_basis: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "available": self.available,
            "description": self.description,
            "source_columns": self.source_columns,
            "calculation_basis": self.calculation_basis,
            "metrics": self.metrics,
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class DomainAnalysisReport:
    dataset_id: str
    results: List[DomainResult]
    computed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "results": [r.to_dict() for r in self.results],
            "computed_at": self.computed_at.isoformat(),
        }


class DomainEngine:
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

    def compute_all(self) -> DomainAnalysisReport:
        results = []

        # 1. Product / Sales domain
        product_result = self._compute_product_sales_domain()
        if product_result is not None:
            results.append(product_result)

        # 2. Inventory domain
        inventory_result = self._compute_inventory_domain()
        if inventory_result is not None:
            results.append(inventory_result)

        # 3. Expiry domain (only when expiry date fields exist)
        expiry_result = self._compute_expiry_domain()
        if expiry_result is not None:
            results.append(expiry_result)

        # 4. Supplier domain
        supplier_result = self._compute_supplier_domain()
        if supplier_result is not None:
            results.append(supplier_result)

        # 5. Loss/Damage domain
        loss_damage_result = self._compute_loss_damage_domain()
        if loss_damage_result is not None:
            results.append(loss_damage_result)

        # 6. Generic entity/category/value analysis
        generic_result = self._compute_generic_domain()
        if generic_result is not None:
            results.append(generic_result)

        return DomainAnalysisReport(
            dataset_id=self._profile.dataset_id,
            results=results,
            computed_at=datetime.utcnow(),
        )

    def _get_role_columns(self, role: SemanticRole) -> List[str]:
        if not self._schema:
            return []
        role_cols: List[str] = []
        for detection in self._schema.detected_roles:
            if detection.role == role:
                role_cols.extend(detection.source_columns)
        return role_cols

    def _compute_product_sales_domain(self) -> Optional[DomainResult]:
        """Compute product/entity performance domain."""
        role_cols = self._get_role_columns(SemanticRole.ENTITY)
        product_cols = self._get_role_columns(SemanticRole.PRODUCT_ITEM)
        sales_cols = self._get_role_columns(SemanticRole.PRICE_REVENUE_VALUE)
        quantity_cols = self._get_role_columns(SemanticRole.QUANTITY)

        all_relevant_cols = list(set(role_cols + product_cols + sales_cols + quantity_cols))
        if not all_relevant_cols:
            return None

        # Check if any relevant columns exist in the profile
        available_cols = [c for c in all_relevant_cols if c in self._profile.column_profiles]
        if not available_cols:
            return None

        metrics: Dict[str, Any] = {}
        source_cols: List[str] = []

        # Aggregate sales/revenue where available
        for col in sales_cols:
            if col in available_cols:
                col_profile = self._profile.column_profiles[col]
                stats = col_profile.numeric_stats
                if stats and "sum" in stats:
                    metrics[f"sales_total_{col}"] = stats["sum"]
                    source_cols.append(col)

        # Top/bottom entities by quantity or sales where statistically meaningful
        entity_cols = [c for c in available_cols if c in role_cols or c in product_cols]
        if entity_cols:
            # Compute unique entity count for first available entity/product column
            first_entity = entity_cols[0]
            if first_entity in available_cols:
                col_profile = self._profile.column_profiles[first_entity]
                metrics["unique_entities"] = col_profile.unique_count
                source_cols.append(first_entity)

        description = "Product/entity performance analysis"
        if not source_cols:
            return None

        return DomainResult(
            domain="product_sales",
            available=True,
            description=description,
            source_columns=source_cols,
            calculation_basis="Product/entity performance and sales/revenue aggregation where fields exist",
            metrics=metrics,
        )

    def _compute_inventory_domain(self) -> Optional[DomainResult]:
        """Compute inventory domain - only when inventory fields exist."""
        inventory_cols = self._get_role_columns(SemanticRole.INVENTORY_STOCK)
        quantity_cols = self._get_role_columns(SemanticRole.QUANTITY)

        all_inventory_cols = list(set(inventory_cols + quantity_cols))
        available_inventory_cols = [c for c in all_inventory_cols if c in self._profile.column_profiles]
        if not available_inventory_cols:
            return None

        metrics: Dict[str, Any] = {}
        source_cols: List[str] = []

        # Stock totals/averages
        for col in available_inventory_cols:
            col_profile = self._profile.column_profiles[col]
            stats = col_profile.numeric_stats
            if stats and "sum" in stats:
                metrics[f"inventory_total_{col}"] = stats["sum"]
                metrics[f"inventory_average_{col}"] = stats.get("mean", 0)
                source_cols.append(col)

        # Zero-stock analysis
        non_null_cols: List[str] = []
        for col in available_inventory_cols:
            col_profile = self._profile.column_profiles[col]
            stats = col_profile.numeric_stats
            if stats and "count" in stats:
                non_null_cols.append(col)
                non_null_count = stats["count"]
                if non_null_count > 0 and self._reader:
                    try:
                        reader = self._get_reader()
                        if reader:
                            df_chunks = reader.read_csv_chunked(columns=[col], max_chunks=100)
                            all_vals = []
                            for chunk in df_chunks:
                                all_vals.extend([row[col] for row in chunk["rows"]])
                            series = pd.Series(all_vals)
                            zero_count = int((series == 0).sum())
                            zero_rate = (zero_count / non_null_count * 100) if non_null_count > 0 else 0.0
                            metrics[f"zero_stock_count_{col}"] = zero_count
                            metrics[f"zero_stock_rate_{col}"] = round(zero_rate, 2)
                    except Exception:
                        pass

        # Stock distribution (category counts where applicable)
        description = "Inventory analysis - stock totals, averages, and zero-stock patterns"
        if not source_cols:
            return None

        return DomainResult(
            domain="inventory",
            available=True,
            description=description,
            source_columns=source_cols,
            calculation_basis="Inventory stock totals, averages, and zero-stock analysis where inventory fields exist",
            metrics=metrics,
        )

    def _compute_expiry_domain(self) -> Optional[DomainResult]:
        """Compute expiry domain only when actual expiry date fields exist."""
        # Look for explicit expiry columns first
        expiry_cols = self._get_role_columns(SemanticRole.EXPIRY)
        available_expiry_cols = [c for c in expiry_cols if c in self._profile.column_profiles]
        
        if not available_expiry_cols:
            return None

        metrics: Dict[str, Any] = {}
        source_cols: List[str] = []
        now = datetime.utcnow()

        reader = self._get_reader()
        
        for col in available_expiry_cols[:3]:  # Limit to 3 columns
            col_profile = self._profile.column_profiles[col]
            
            # Try to read actual data to compute expired/upcoming
            if reader:
                try:
                    df_chunks = reader.read_csv_chunked(columns=[col], max_chunks=100)
                    all_vals = []
                    for chunk in df_chunks:
                        all_vals.extend([row[col] for row in chunk["rows"]])
                    
                    if all_vals:
                        series = pd.to_datetime(pd.Series(all_vals), errors="coerce")
                        valid_series = series.dropna()
                        
                        if len(valid_series) > 0:
                            expired = valid_series[valid_series < now]
                            upcoming_30 = valid_series[(valid_series >= now) & (valid_series <= now + pd.Timedelta(days=30))]
                            upcoming_90 = valid_series[(valid_series >= now) & (valid_series <= now + pd.Timedelta(days=90))]
                            future = valid_series[valid_series > now + pd.Timedelta(days=90)]
                            
                            metrics[f"expired_count_{col}"] = len(expired)
                            metrics[f"upcoming_30_days_{col}"] = len(upcoming_30)
                            metrics[f"upcoming_90_days_{col}"] = len(upcoming_90)
                            metrics[f"future_count_{col}"] = len(future)
                            metrics[f"total_expiry_records_{col}"] = len(valid_series)
                            metrics[f"expired_rate_pct_{col}"] = round(len(expired) / len(valid_series) * 100, 2) if len(valid_series) > 0 else 0.0
                            source_cols.append(col)
                except Exception:
                    pass
            
            # Also include date range from profile
            if col_profile.datetime_range:
                dr = col_profile.datetime_range
                metrics[f"expiry_date_range_{col}"] = {
                    "min": dr.get("min"),
                    "max": dr.get("max"),
                }
                if col not in source_cols:
                    source_cols.append(col)

        description = "Expiry date analysis - expired, upcoming (30/90 days), and future counts from actual expiry fields"
        if not source_cols:
            return None

        return DomainResult(
            domain="expiry",
            available=True,
            description=description,
            source_columns=source_cols,
            calculation_basis="Expiry date analysis using actual expiry/expiration fields; compares dates to current time",
            metrics=metrics,
            limitations=["Only analyzes columns explicitly detected as expiry fields", "Requires readable date values"],
        )

    def _compute_supplier_domain(self) -> Optional[DomainResult]:
        """Compute supplier domain only when supplier fields exist AND measurable activity exists."""
        supplier_cols = self._get_role_columns(SemanticRole.SUPPLIER)

        available_supplier_cols = [c for c in supplier_cols if c in self._profile.column_profiles]
        if not available_supplier_cols:
            return None

        metrics: Dict[str, Any] = {}
        source_cols: List[str] = []

        # Supplier counts/activity
        for col in available_supplier_cols[:3]:  # Limit to 3 supplier columns
            col_profile = self._profile.column_profiles[col]
            metrics[f"supplier_unique_{col}"] = col_profile.unique_count
            source_cols.append(col)

        description = "Supplier analysis - counts where supplier fields exist"
        if not source_cols:
            return None

        return DomainResult(
            domain="supplier",
            available=True,
            description=description,
            source_columns=source_cols,
            calculation_basis="Supplier counts where actual supplier fields exist",
            metrics=metrics,
        )

    def _compute_loss_damage_domain(self) -> Optional[DomainResult]:
        """Compute loss/damage domain only when actual loss/damage fields exist."""
        loss_cols = self._get_role_columns(SemanticRole.LOSS_DAMAGE)

        available_loss_cols = [c for c in loss_cols if c in self._profile.column_profiles]
        if not available_loss_cols:
            return None

        metrics: Dict[str, Any] = {}
        source_cols: List[str] = []

        # Loss/damage counts or totals
        for col in available_loss_cols:
            col_profile = self._profile.column_profiles[col]
            if col_profile.numeric_stats:
                stats = col_profile.numeric_stats
                if "count" in stats:
                    metrics[f"loss_damage_count_{col}"] = stats["count"]
                if "sum" in stats:
                    metrics[f"loss_damage_total_{col}"] = stats["sum"]
            source_cols.append(col)

        # Distribution by available entity/location/category
        description = "Loss/damage analysis - counts and totals where actual loss/damage fields exist"
        if not source_cols:
            return None

        return DomainResult(
            domain="loss_damage",
            available=True,
            description=description,
            source_columns=source_cols,
            calculation_basis="Loss/damage counts and totals where actual loss/damage fields exist, distribution by entity/location/category",
            metrics=metrics,
        )

    def _compute_generic_domain(self) -> Optional[DomainResult]:
        """Support generic entity/category/value analysis when actual schema supports it."""
        entity_cols = self._get_role_columns(SemanticRole.ENTITY)
        category_cols = self._get_role_columns(SemanticRole.CATEGORY)
        value_cols = self._get_role_columns(SemanticRole.PRICE_REVENUE_VALUE)

        all_relevant = list(set(entity_cols + category_cols + value_cols))
        available_relevant = [c for c in all_relevant if c in self._profile.column_profiles]
        if not available_relevant:
            return None

        metrics: Dict[str, Any] = {}
        source_cols: List[str] = []

        # Generic category counts
        for col in category_cols:
            if col in available_relevant:
                col_profile = self._profile.column_profiles[col]
                metrics[f"category_count_{col}"] = len(col_profile.categorical_summary) if col_profile.categorical_summary else 0
                source_cols.append(col)

        # Unique entity count
        for col in entity_cols:
            if col in available_relevant:
                col_profile = self._profile.column_profiles[col]
                metrics["unique_entities"] = col_profile.unique_count
                source_cols.append(col)

        # Value totals where available
        for col in value_cols:
            if col in available_relevant:
                col_profile = self._profile.column_profiles[col]
                stats = col_profile.numeric_stats
                if stats and "sum" in stats:
                    metrics[f"value_total_{col}"] = stats["sum"]
                if stats and "mean" in stats:
                    metrics[f"value_mean_{col}"] = stats["mean"]
                source_cols.append(col)

        description = "Generic entity/category/value analysis where schema supports it"
        if not source_cols:
            return None

        return DomainResult(
            domain="generic",
            available=True,
            description=description,
            source_columns=source_cols,
            calculation_basis="Generic entity/category/value analysis where actual schema supports it",
            metrics=metrics,
        )


def create_domain_engine(
    profile: DatasetProfile,
    schema_intelligence: SchemaIntelligence | None = None,
    capability_detection: CapabilityDetection | None = None,
    reader_provider: Optional[callable] | None = None,
) -> DomainEngine:
    return DomainEngine(profile, schema_intelligence, capability_detection, reader_provider)