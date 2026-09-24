from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
import uuid


class DatasetStatus(str, Enum):
    UPLOADING = "uploading"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"
    EXPIRED = "expired"


class FileFormat(str, Enum):
    CSV = "csv"
    XLS = "xls"
    XLSX = "xlsx"


class InferredType(str, Enum):
    INTEGER = "integer"
    FLOAT = "float"
    NUMERIC = "numeric"
    STRING = "string"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"
    UNKNOWN = "unknown"


class SemanticRole(str, Enum):
    ID_KEY = "id_key"
    ENTITY = "entity"
    PRODUCT_ITEM = "product_item"
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    QUANTITY = "quantity"
    PRICE_REVENUE_VALUE = "price_revenue_value"
    DATE_TIME = "date_time"
    CATEGORY = "category"
    STATUS = "status"
    INVENTORY_STOCK = "inventory_stock"
    ORIGIN = "origin"
    DESTINATION = "destination"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    LOSS_DAMAGE = "loss_damage"
    EXPIRY = "expiry"
    DELIVERY_SHIPMENT = "delivery_shipment"
    UNKNOWN = "unknown"


class CapabilityStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DatasetMetadata:
    dataset_id: str
    original_filename: str
    file_format: FileFormat
    file_size_bytes: int
    content_hash: str
    created_at: datetime
    expires_at: datetime
    status: DatasetStatus = DatasetStatus.UPLOADING
    row_count: int | None = None
    column_count: int | None = None
    column_names: list[str] = field(default_factory=list)
    column_types: dict[str, str] = field(default_factory=dict)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "original_filename": self.original_filename,
            "file_format": self.file_format.value,
            "file_size_bytes": self.file_size_bytes,
            "content_hash": self.content_hash,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "status": self.status.value,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "column_names": self.column_names,
            "column_types": self.column_types,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetMetadata:
        return cls(
            dataset_id=data["dataset_id"],
            original_filename=data["original_filename"],
            file_format=FileFormat(data["file_format"]),
            file_size_bytes=data["file_size_bytes"],
            content_hash=data["content_hash"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            status=DatasetStatus(data["status"]),
            row_count=data.get("row_count"),
            column_count=data.get("column_count"),
            column_names=data.get("column_names", []),
            column_types=data.get("column_types", {}),
            error_message=data.get("error_message"),
        )


@dataclass(frozen=True)
class DatasetSession:
    metadata: DatasetMetadata
    storage_path: Path

    @property
    def dataset_id(self) -> str:
        return self.metadata.dataset_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "storage_path": str(self.storage_path),
        }


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    inferred_type: InferredType
    pandas_dtype: str
    null_count: int
    null_percentage: float
    unique_count: int
    duplicate_count: int = 0
    sample_values: list[Any] = field(default_factory=list)

    numeric_stats: dict[str, float] | None = None
    categorical_summary: dict[str, int] | None = None
    datetime_range: dict[str, str] | None = None
    boolean_distribution: dict[str, int] | None = None

    is_id_candidate: bool = False
    is_geographic_candidate: bool = False
    is_measure_candidate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "inferred_type": self.inferred_type.value,
            "pandas_dtype": self.pandas_dtype,
            "null_count": self.null_count,
            "null_percentage": self.null_percentage,
            "unique_count": self.unique_count,
            "duplicate_count": self.duplicate_count,
            "sample_values": self.sample_values[:10] if self.sample_values else [],
            "numeric_stats": self.numeric_stats,
            "categorical_summary": self.categorical_summary,
            "datetime_range": self.datetime_range,
            "boolean_distribution": self.boolean_distribution,
            "is_id_candidate": self.is_id_candidate,
            "is_geographic_candidate": self.is_geographic_candidate,
            "is_measure_candidate": self.is_measure_candidate,
        }


@dataclass(frozen=True)
class DatasetProfile:
    dataset_id: str
    row_count: int
    column_count: int
    column_names: list[str]
    column_profiles: dict[str, ColumnProfile]
    duplicate_row_count: int
    numeric_columns: list[str]
    categorical_columns: list[str]
    datetime_columns: list[str]
    boolean_columns: list[str]
    id_key_candidates: list[str]
    measure_candidates: list[str]
    geographic_candidates: list[str]
    profiled_at: datetime
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "column_names": self.column_names,
            "column_profiles": {k: v.to_dict() for k, v in self.column_profiles.items()},
            "duplicate_row_count": self.duplicate_row_count,
            "numeric_columns": self.numeric_columns,
            "categorical_columns": self.categorical_columns,
            "datetime_columns": self.datetime_columns,
            "boolean_columns": self.boolean_columns,
            "id_key_candidates": self.id_key_candidates,
            "measure_candidates": self.measure_candidates,
            "geographic_candidates": self.geographic_candidates,
            "profiled_at": self.profiled_at.isoformat(),
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class SemanticRoleDetection:
    role: SemanticRole
    source_columns: list[str]
    confidence: float
    evidence: dict[str, Any]
    uncertainty: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "source_columns": self.source_columns,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "uncertainty": self.uncertainty,
        }


@dataclass(frozen=True)
class SchemaIntelligence:
    dataset_id: str
    detected_roles: list[SemanticRoleDetection]
    column_roles: dict[str, list[SemanticRole]]
    analyzed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "detected_roles": [r.to_dict() for r in self.detected_roles],
            "column_roles": {k: [r.value for r in v] for k, v in self.column_roles.items()},
            "analyzed_at": self.analyzed_at.isoformat(),
        }


@dataclass(frozen=True)
class Capability:
    name: str
    status: CapabilityStatus
    required_fields: list[str]
    detected_fields: list[str]
    evidence: dict[str, Any]
    confidence: float
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "required_fields": self.required_fields,
            "detected_fields": self.detected_fields,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CapabilityDetection:
    dataset_id: str
    capabilities: list[Capability]
    analyzed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "analyzed_at": self.analyzed_at.isoformat(),
        }


def generate_dataset_id() -> str:
    return f"ds_{uuid.uuid4().hex[:16]}"


def generate_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:16]}"