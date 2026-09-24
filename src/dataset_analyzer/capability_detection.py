from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from dataset_analyzer.models import (
    Capability,
    CapabilityDetection,
    CapabilityStatus,
    DatasetProfile,
    SchemaIntelligence,
    SemanticRole,
)


@dataclass
class CapabilityRule:
    name: str
    required_roles: list[SemanticRole]
    optional_roles: list[SemanticRole]
    description: str


CAPABILITY_RULES: list[CapabilityRule] = [
    CapabilityRule(
        name="trend_analysis",
        required_roles=[SemanticRole.DATE_TIME],
        optional_roles=[SemanticRole.PRICE_REVENUE_VALUE, SemanticRole.QUANTITY, SemanticRole.INVENTORY_STOCK, SemanticRole.ENTITY, SemanticRole.PRODUCT_ITEM, SemanticRole.CUSTOMER, SemanticRole.CATEGORY],
        description="Time-series trend analysis requires a date/time column and at least one numeric measure column",
    ),
    CapabilityRule(
        name="inventory_analysis",
        required_roles=[SemanticRole.INVENTORY_STOCK],
        optional_roles=[SemanticRole.PRODUCT_ITEM, SemanticRole.DATE_TIME, SemanticRole.ENTITY, SemanticRole.CATEGORY],
        description="Inventory analysis requires a stock/inventory column",
    ),
    CapabilityRule(
        name="expiry_analysis",
        required_roles=[SemanticRole.EXPIRY],
        optional_roles=[SemanticRole.PRODUCT_ITEM, SemanticRole.ENTITY, SemanticRole.INVENTORY_STOCK, SemanticRole.CATEGORY],
        description="Expiry analysis requires an expiry date column",
    ),
    CapabilityRule(
        name="geospatial_analysis",
        required_roles=[SemanticRole.LATITUDE, SemanticRole.LONGITUDE],
        optional_roles=[SemanticRole.ENTITY, SemanticRole.CATEGORY, SemanticRole.PRICE_REVENUE_VALUE],
        description="Geospatial analysis requires both latitude and longitude columns",
    ),
    CapabilityRule(
        name="route_analysis",
        required_roles=[SemanticRole.ORIGIN, SemanticRole.DESTINATION],
        optional_roles=[SemanticRole.DATE_TIME, SemanticRole.ENTITY, SemanticRole.DELIVERY_SHIPMENT, SemanticRole.PRICE_REVENUE_VALUE],
        description="Route analysis requires origin and destination columns",
    ),
    CapabilityRule(
        name="supplier_analysis",
        required_roles=[SemanticRole.SUPPLIER],
        optional_roles=[SemanticRole.QUANTITY, SemanticRole.PRICE_REVENUE_VALUE, SemanticRole.DATE_TIME, SemanticRole.STATUS, SemanticRole.DELIVERY_SHIPMENT],
        description="Supplier analysis requires a supplier column and measurable activity",
    ),
    CapabilityRule(
        name="loss_analysis",
        required_roles=[SemanticRole.LOSS_DAMAGE],
        optional_roles=[SemanticRole.ENTITY, SemanticRole.ORIGIN, SemanticRole.DESTINATION, SemanticRole.LATITUDE, SemanticRole.LONGITUDE, SemanticRole.DATE_TIME],
        description="Loss analysis requires a loss/damage indicator and relevant entity/location",
    ),
    CapabilityRule(
        name="statistical_analysis",
        required_roles=[],
        optional_roles=[SemanticRole.PRICE_REVENUE_VALUE, SemanticRole.QUANTITY, SemanticRole.INVENTORY_STOCK],
        description="Statistical analysis requires numeric fields",
    ),
    CapabilityRule(
        name="categorical_analysis",
        required_roles=[],
        optional_roles=[SemanticRole.CATEGORY, SemanticRole.STATUS, SemanticRole.PRODUCT_ITEM, SemanticRole.CUSTOMER, SemanticRole.SUPPLIER],
        description="Categorical analysis requires categorical fields",
    ),
]


class CapabilityDetector:
    def __init__(self, profile: DatasetProfile, schema_intelligence: SchemaIntelligence):
        self._profile = profile
        self._schema = schema_intelligence
        self._roles_by_column = self._build_role_index()

    def _build_role_index(self) -> dict[str, list[SemanticRoleDetection]]:
        index: dict[str, list[SemanticRoleDetection]] = {}
        for detection in self._schema.detected_roles:
            for col in detection.source_columns:
                if col not in index:
                    index[col] = []
                index[col].append(detection)
        return index

    def _has_role(self, role: SemanticRole) -> tuple[bool, list[str], list[dict[str, Any]]]:
        detected_columns = []
        evidence_list = []
        for detection in self._schema.detected_roles:
            if detection.role == role:
                detected_columns.extend(detection.source_columns)
                evidence_list.append({
                    "columns": detection.source_columns,
                    "confidence": detection.confidence,
                    "evidence": detection.evidence,
                })
        return len(detected_columns) > 0, detected_columns, evidence_list

    def _has_numeric_fields(self) -> tuple[bool, list[str], list[dict[str, Any]]]:
        detected = self._profile.numeric_columns
        evidence = [{"columns": detected, "count": len(detected), "types": "numeric"}]
        return len(detected) > 0, detected, evidence

    def _has_categorical_fields(self) -> tuple[bool, list[str], list[dict[str, Any]]]:
        detected = self._profile.categorical_columns
        evidence = [{"columns": detected, "count": len(detected), "types": "categorical"}]
        return len(detected) > 0, detected, evidence

    def detect_all(self) -> CapabilityDetection:
        capabilities = []

        for rule in CAPABILITY_RULES:
            capability = self._evaluate_rule(rule)
            capabilities.append(capability)

        return CapabilityDetection(
            dataset_id=self._profile.dataset_id,
            capabilities=capabilities,
            analyzed_at=datetime.utcnow(),
        )

    def _evaluate_rule(self, rule: CapabilityRule) -> Capability:
        all_required_met = True
        required_fields_found = []
        required_evidence = []

        for required_role in rule.required_roles:
            has_role, columns, evidence = self._has_role(required_role)
            if has_role:
                required_fields_found.extend(columns)
                required_evidence.extend(evidence)
            else:
                all_required_met = False

        optional_fields_found = []
        optional_evidence = []
        for optional_role in rule.optional_roles:
            has_role, columns, evidence = self._has_role(optional_role)
            if has_role:
                optional_fields_found.extend(columns)
                optional_evidence.extend(evidence)

        if rule.name == "statistical_analysis":
            has_numeric, numeric_cols, numeric_evidence = self._has_numeric_fields()
            if has_numeric:
                optional_fields_found.extend(numeric_cols)
                optional_evidence.extend(numeric_evidence)
            else:
                all_required_met = False

        if rule.name == "categorical_analysis":
            has_categorical, cat_cols, cat_evidence = self._has_categorical_fields()
            if has_categorical:
                optional_fields_found.extend(cat_cols)
                optional_evidence.extend(cat_evidence)
            else:
                all_required_met = False

        if rule.name == "trend_analysis":
            has_measure = False
            measure_roles = [SemanticRole.PRICE_REVENUE_VALUE, SemanticRole.QUANTITY, SemanticRole.INVENTORY_STOCK]
            for mr in measure_roles:
                has_role, columns, evidence = self._has_role(mr)
                if has_role:
                    has_measure = True
                    optional_fields_found.extend(columns)
                    optional_evidence.extend(evidence)
            if not has_measure:
                has_numeric, numeric_cols, numeric_evidence = self._has_numeric_fields()
                if has_numeric:
                    has_measure = True
                    optional_fields_found.extend(numeric_cols)
                    optional_evidence.extend(numeric_evidence)
            if not has_measure:
                all_required_met = False

        all_detected = list(set(required_fields_found + optional_fields_found))

        if all_required_met:
            confidence = self._compute_confidence(rule, required_evidence, optional_evidence)
            return Capability(
                name=rule.name,
                status=CapabilityStatus.AVAILABLE,
                required_fields=self._get_required_field_names(rule),
                detected_fields=all_detected,
                evidence={
                    "required": required_evidence,
                    "optional": optional_evidence,
                    "rule_description": rule.description,
                },
                confidence=confidence,
            )
        else:
            missing = self._get_missing_required_fields(rule)
            return Capability(
                name=rule.name,
                status=CapabilityStatus.UNAVAILABLE,
                required_fields=self._get_required_field_names(rule),
                detected_fields=all_detected,
                evidence={
                    "required": required_evidence,
                    "optional": optional_evidence,
                    "rule_description": rule.description,
                    "missing_fields": missing,
                },
                confidence=0.0,
                reason=f"Analysis unavailable — required field(s) not detected: {', '.join(missing)}",
            )

    def _compute_confidence(
        self, rule: CapabilityRule, required_evidence: list[dict], optional_evidence: list[dict]
    ) -> float:
        if not required_evidence:
            return 0.5

        required_confidences = [e.get("confidence", 0.5) for e in required_evidence]
        avg_required = sum(required_confidences) / len(required_confidences) if required_confidences else 0.5

        optional_confidences = [e.get("confidence", 0.5) for e in optional_evidence]
        avg_optional = sum(optional_confidences) / len(optional_confidences) if optional_confidences else 0.0

        return round(0.7 * avg_required + 0.3 * avg_optional, 2)

    def _get_required_field_names(self, rule: CapabilityRule) -> list[str]:
        names = []
        for role in rule.required_roles:
            names.append(role.value)
        if rule.name == "statistical_analysis":
            names.append("numeric_fields")
        if rule.name == "categorical_analysis":
            names.append("categorical_fields")
        if rule.name == "trend_analysis":
            names.append("numeric_measure_fields")
        return names

    def _get_missing_required_fields(self, rule: CapabilityRule) -> list[str]:
        missing = []
        for required_role in rule.required_roles:
            has_role, _, _ = self._has_role(required_role)
            if not has_role:
                missing.append(required_role.value)
        if rule.name == "statistical_analysis":
            has_numeric, _, _ = self._has_numeric_fields()
            if not has_numeric:
                missing.append("numeric_fields")
        if rule.name == "categorical_analysis":
            has_categorical, _, _ = self._has_categorical_fields()
            if not has_categorical:
                missing.append("categorical_fields")
        if rule.name == "trend_analysis":
            has_measure = False
            measure_roles = [SemanticRole.PRICE_REVENUE_VALUE, SemanticRole.QUANTITY, SemanticRole.INVENTORY_STOCK]
            for mr in measure_roles:
                has_role, _, _ = self._has_role(mr)
                if has_role:
                    has_measure = True
                    break
            if not has_measure:
                has_numeric, _, _ = self._has_numeric_fields()
                if has_numeric:
                    has_measure = True
            if not has_measure:
                missing.append("numeric_measure_fields")
        return missing


def create_capability_detector(profile: DatasetProfile, schema_intelligence: SchemaIntelligence) -> CapabilityDetector:
    return CapabilityDetector(profile, schema_intelligence)