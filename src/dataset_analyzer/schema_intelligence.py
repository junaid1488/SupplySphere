from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import re

import pandas as pd

from dataset_analyzer.models import (
    ColumnProfile,
    DatasetProfile,
    SemanticRole,
    SemanticRoleDetection,
    SchemaIntelligence,
    InferredType,
)


@dataclass
class RoleEvidence:
    role: SemanticRole
    confidence: float
    evidence: dict[str, Any]
    uncertainty: str | None = None


class SchemaIntelligenceAnalyzer:
    def __init__(self, profile: DatasetProfile):
        self._profile = profile

    def analyze(self) -> SchemaIntelligence:
        detected_roles = []
        column_roles: dict[str, list[SemanticRole]] = {}

        for col_name, col_profile in self._profile.column_profiles.items():
            roles = self._detect_roles_for_column(col_name, col_profile)
            for role in roles:
                detected_roles.append(role)
                if col_name not in column_roles:
                    column_roles[col_name] = []
                column_roles[col_name].append(role.role)

        return SchemaIntelligence(
            dataset_id=self._profile.dataset_id,
            detected_roles=detected_roles,
            column_roles=column_roles,
            analyzed_at=datetime.utcnow(),
        )

    def _detect_roles_for_column(self, col_name: str, profile: ColumnProfile) -> list[SemanticRoleDetection]:
        roles = []
        name_lower = col_name.lower()

        if profile.is_id_candidate:
            roles.append(self._create_detection(
                SemanticRole.ID_KEY,
                [col_name],
                0.8,
                {"reason": "High uniqueness ratio and/or ID-like column name", "uniqueness": profile.unique_count / max(self._profile.row_count, 1)},
                uncertainty="Could be a surrogate key or natural key; verify business context"
            ))

        if self._is_entity_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.ENTITY,
                [col_name],
                0.6,
                {"reason": "Column name suggests entity identifier", "name_pattern": name_lower},
                uncertainty="Entity role inferred from name only; confirm with domain knowledge"
            ))

        if self._is_product_item_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.PRODUCT_ITEM,
                [col_name],
                0.7,
                {"reason": "Column name suggests product/item", "name_pattern": name_lower},
                uncertainty="Product role inferred from name only"
            ))

        if self._is_customer_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.CUSTOMER,
                [col_name],
                0.7,
                {"reason": "Column name suggests customer", "name_pattern": name_lower},
                uncertainty="Customer role inferred from name only"
            ))

        if self._is_supplier_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.SUPPLIER,
                [col_name],
                0.7,
                {"reason": "Column name suggests supplier", "name_pattern": name_lower},
                uncertainty="Supplier role inferred from name only"
            ))

        if self._is_quantity_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.QUANTITY,
                [col_name],
                0.75,
                {"reason": "Column name suggests quantity", "name_pattern": name_lower, "is_numeric": profile.inferred_type in (InferredType.INTEGER, InferredType.FLOAT, InferredType.NUMERIC)},
                uncertainty="Quantity role inferred from name; verify numeric values represent counts"
            ))

        if self._is_price_revenue_value_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.PRICE_REVENUE_VALUE,
                [col_name],
                0.75,
                {"reason": "Column name suggests price/revenue/value", "name_pattern": name_lower, "is_numeric": profile.inferred_type in (InferredType.INTEGER, InferredType.FLOAT, InferredType.NUMERIC)},
                uncertainty="Price/revenue role inferred from name; verify units and currency"
            ))

        if self._is_date_time_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.DATE_TIME,
                [col_name],
                0.9 if profile.inferred_type in (InferredType.DATETIME, InferredType.DATE, InferredType.TIME) else 0.5,
                {"reason": "Column name or type suggests date/time", "name_pattern": name_lower, "inferred_type": profile.inferred_type.value},
                uncertainty="Date/time role inferred from name; verify format consistency"
            ))

        if self._is_category_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.CATEGORY,
                [col_name],
                0.7,
                {"reason": "Column name suggests category", "name_pattern": name_lower, "unique_count": profile.unique_count},
                uncertainty="Category role inferred from name; verify cardinality is appropriate"
            ))

        if self._is_status_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.STATUS,
                [col_name],
                0.7,
                {"reason": "Column name suggests status", "name_pattern": name_lower, "unique_count": profile.unique_count},
                uncertainty="Status role inferred from name; verify values represent states"
            ))

        if self._is_inventory_stock_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.INVENTORY_STOCK,
                [col_name],
                0.7,
                {"reason": "Column name suggests inventory/stock", "name_pattern": name_lower, "is_numeric": profile.inferred_type in (InferredType.INTEGER, InferredType.FLOAT, InferredType.NUMERIC)},
                uncertainty="Inventory role inferred from name; verify values represent stock levels"
            ))

        if self._is_origin_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.ORIGIN,
                [col_name],
                0.65,
                {"reason": "Column name suggests origin", "name_pattern": name_lower},
                uncertainty="Origin role inferred from name only"
            ))

        if self._is_destination_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.DESTINATION,
                [col_name],
                0.65,
                {"reason": "Column name suggests destination", "name_pattern": name_lower},
                uncertainty="Destination role inferred from name only"
            ))

        if self._is_latitude_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.LATITUDE,
                [col_name],
                0.8,
                {"reason": "Column name suggests latitude", "name_pattern": name_lower, "value_range_valid": profile.is_geographic_candidate},
                uncertainty="Latitude role inferred from name; verify value range [-90, 90]"
            ))

        if self._is_longitude_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.LONGITUDE,
                [col_name],
                0.8,
                {"reason": "Column name suggests longitude", "name_pattern": name_lower, "value_range_valid": profile.is_geographic_candidate},
                uncertainty="Longitude role inferred from name; verify value range [-180, 180]"
            ))

        if self._is_loss_damage_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.LOSS_DAMAGE,
                [col_name],
                0.7,
                {"reason": "Column name suggests loss/damage indicator", "name_pattern": name_lower},
                uncertainty="Loss/damage role inferred from name only"
            ))

        if self._is_expiry_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.EXPIRY,
                [col_name],
                0.75,
                {"reason": "Column name suggests expiry date", "name_pattern": name_lower, "inferred_type": profile.inferred_type.value},
                uncertainty="Expiry role inferred from name; verify values are future dates"
            ))

        if self._is_delivery_shipment_column(name_lower, profile):
            roles.append(self._create_detection(
                SemanticRole.DELIVERY_SHIPMENT,
                [col_name],
                0.7,
                {"reason": "Column name suggests delivery/shipment", "name_pattern": name_lower, "inferred_type": profile.inferred_type.value},
                uncertainty="Delivery/shipment role inferred from name only"
            ))

        return roles

    def _create_detection(
        self,
        role: SemanticRole,
        source_columns: list[str],
        confidence: float,
        evidence: dict[str, Any],
        uncertainty: str | None = None,
    ) -> SemanticRoleDetection:
        return SemanticRoleDetection(
            role=role,
            source_columns=source_columns,
            confidence=confidence,
            evidence=evidence,
            uncertainty=uncertainty,
        )

    def _is_entity_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        entity_keywords = ["entity", "object", "item", "asset", "resource"]
        return any(kw in name_lower for kw in entity_keywords)

    def _is_product_item_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        product_keywords = ["product", "item", "sku", "goods", "merchandise", "article"]
        return any(kw in name_lower for kw in product_keywords)

    def _is_customer_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        customer_keywords = ["customer", "client", "buyer", "purchaser", "consumer", "user"]
        return any(kw in name_lower for kw in customer_keywords)

    def _is_supplier_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        supplier_keywords = ["supplier", "vendor", "seller", "provider", "manufacturer"]
        return any(kw in name_lower for kw in supplier_keywords)

    def _is_quantity_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        quantity_keywords = ["quantity", "qty", "amount", "volume", "units", "num_", "number_of"]
        if any(kw in name_lower for kw in quantity_keywords):
            return True
        if re.search(r'(?<!\w)count(?!\w)', name_lower):
            return True
        return False

    def _is_price_revenue_value_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        revenue_keywords = ["revenue", "sales", "gross", "net", "turnover", "income", "total_sales", "total_revenue"]
        return any(kw in name_lower for kw in revenue_keywords)

    def _is_date_time_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        # Columns identified as ID candidates should never be treated as datetime
        if profile.is_id_candidate:
            return False
        date_keywords = ["date", "time", "timestamp", "created", "updated", "modified", "order_date", "ship_date", "delivery_date"]
        if any(kw in name_lower for kw in date_keywords):
            return True
        return profile.inferred_type in (InferredType.DATETIME, InferredType.DATE, InferredType.TIME)

    def _is_category_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        category_keywords = ["category", "type", "class", "group", "segment", "genre", "kind", "classification"]
        if any(kw in name_lower for kw in category_keywords):
            return True
        if profile.inferred_type == InferredType.STRING and profile.unique_count < self._profile.row_count * 0.5:
            return True
        return False

    def _is_status_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        status_keywords = ["status", "state", "condition", "flag", "is_", "has_", "active", "enabled"]
        return any(kw in name_lower for kw in status_keywords)

    def _is_inventory_stock_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        stock_keywords = ["stock", "inventory", "on_hand", "available", "quantity_on_hand", "qoh", "level"]
        if any(kw in name_lower for kw in stock_keywords):
            if profile.inferred_type in (InferredType.INTEGER, InferredType.FLOAT, InferredType.NUMERIC):
                return True
        return False

    def _is_origin_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        # Full-word matches
        full_keywords = ["origin", "departure", "pickup"]
        for kw in full_keywords:
            if kw in name_lower:
                return True
        # Word-boundary matches for shorter keywords
        if re.search(r'(?<![a-z])from_(?![a-z])', name_lower):
            return True
        return False

    def _is_destination_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        # Full-word matches
        full_keywords = ["destination", "arrival", "dropoff", "drop_off"]
        for kw in full_keywords:
            if kw in name_lower:
                return True
        # Word-boundary matches for shorter keywords
        if re.search(r'(?<![a-z])dest(?![a-z])', name_lower):
            return True
        if re.search(r'(?<![a-z])to_(?![a-z])', name_lower):
            return True
        if re.search(r'(?<![a-z])delivery(?![a-z])', name_lower):
            return True
        return False

    def _is_latitude_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        lat_keywords = ["latitude"]
        for kw in lat_keywords:
            if kw in name_lower:
                return True
        # For short keyword "lat", require word boundary to avoid matching "late", "latent", etc.
        if re.search(r'(?<![a-z])lat(?![a-z])', name_lower):
            return True
        return False

    def _is_longitude_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        lon_keywords = ["longitude"]
        for kw in lon_keywords:
            if kw in name_lower:
                return True
        # For short keywords, require word boundary to avoid false matches
        if re.search(r'(?<![a-z])lon(?![a-z])', name_lower):
            return True
        if re.search(r'(?<![a-z])lng(?![a-z])', name_lower):
            return True
        if re.search(r'(?<![a-z])long(?![a-z_])', name_lower):
            return True
        return False

    def _is_loss_damage_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        loss_keywords = ["loss", "damage", "damaged", "defect", "broken", "lost", "shrinkage", "waste"]
        return any(kw in name_lower for kw in loss_keywords)

    def _is_expiry_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        expiry_keywords = ["expiry", "expiration", "expire", "exp_date", "best_before", "use_by", "shelf_life"]
        return any(kw in name_lower for kw in expiry_keywords)

    def _is_delivery_shipment_column(self, name_lower: str, profile: ColumnProfile) -> bool:
        delivery_keywords = ["delivery", "shipment", "ship", "dispatch", "tracking", "carrier", "logistics"]
        return any(kw in name_lower for kw in delivery_keywords)


def create_schema_intelligence_analyzer(profile: DatasetProfile) -> SchemaIntelligenceAnalyzer:
    return SchemaIntelligenceAnalyzer(profile)