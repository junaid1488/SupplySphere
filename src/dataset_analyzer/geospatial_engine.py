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


@dataclass(frozen=True)
class GeospatialResult:
    valid_coordinate_count: int
    invalid_coordinate_count: int
    total_records: int
    bounding_box: Dict[str, float]
    coordinate_distribution: Dict[str, Any]
    valid_percentage: float
    source_columns: List[str]
    calculation_basis: str
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid_coordinate_count": self.valid_coordinate_count,
            "invalid_coordinate_count": self.invalid_coordinate_count,
            "total_records": self.total_records,
            "bounding_box": self.bounding_box,
            "coordinate_distribution": self.coordinate_distribution,
            "valid_percentage": self.valid_percentage,
            "source_columns": self.source_columns,
            "calculation_basis": self.calculation_basis,
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class OriginDestinationSummary:
    unique_origins: int
    unique_destinations: int
    unique_routes: int
    origin_distribution: Dict[str, Any]
    destination_distribution: Dict[str, Any]
    source_columns: List[str]
    calculation_basis: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "unique_origins": self.unique_origins,
            "unique_destinations": self.unique_destinations,
            "unique_routes": self.unique_routes,
            "origin_distribution": self.origin_distribution,
            "destination_distribution": self.destination_distribution,
            "source_columns": self.source_columns,
            "calculation_basis": self.calculation_basis,
        }


@dataclass(frozen=True)
class GeospatialAnalysisReport:
    dataset_id: str
    geospatial: GeospatialResult
    origin_destination: Optional[OriginDestinationSummary] = None
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "dataset_id": self.dataset_id,
            "geospatial": self.geospatial.to_dict(),
            "computed_at": self.computed_at.isoformat(),
        }
        if self.origin_destination is not None:
            result["origin_destination"] = self.origin_destination.to_dict()
        return result


class GeospatialEngine:
    def __init__(
        self,
        profile: DatasetProfile,
        schema_intelligence: SchemaIntelligence | None = None,
        reader_provider: Optional[callable] | None = None,
    ):
        self._profile = profile
        self._schema = schema_intelligence
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

    def _get_geo_columns(self) -> Tuple[Optional[str], Optional[str]]:
        """Get latitude and longitude column names from schema or geographic candidates."""
        lat_cols = self._get_role_columns(SemanticRole.LATITUDE)
        lon_cols = self._get_role_columns(SemanticRole.LONGITUDE)

        # If schema has explicit lat/lon, use those
        if lat_cols and lon_cols:
            return lat_cols[0], lon_cols[0]

        # Fall back to geographic candidates from profile
        geo_candidates = self._profile.geographic_candidates
        if len(geo_candidates) >= 2:
            return geo_candidates[0], geo_candidates[1]

        return None, None

    def _get_role_columns(self, role: SemanticRole) -> List[str]:
        if not self._schema:
            return []
        role_cols: List[str] = []
        for detection in self._schema.detected_roles:
            if detection.role == role:
                role_cols.extend(detection.source_columns)
        return role_cols

    def compute_all(self) -> GeospatialAnalysisReport:
        lat_col, lon_col = self._get_geo_columns()

        # Compute core geospatial analysis
        geo_result = self._compute_geospatial_summary(lat_col, lon_col)

        # Compute origin/destination geographic summaries if origin/destination columns exist
        od_result = self._compute_origin_destination_geographic()

        return GeospatialAnalysisReport(
            dataset_id=self._profile.dataset_id,
            geospatial=geo_result,
            origin_destination=od_result,
        )

    def _compute_geospatial_summary(
        self, lat_col: Optional[str], lon_col: Optional[str]
    ) -> GeospatialResult:
        """Compute geographic summary: valid/invalid coordinates, bounding box, distribution."""
        total_records = 0
        valid_count = 0
        invalid_count = 0
        all_lats: List[float] = []
        all_lons: List[float] = []

        if lat_col and lon_col and lat_col in self._profile.column_profiles and lon_col in self._profile.column_profiles:
            reader = self._get_reader()
            if reader:
                try:
                    df_chunks = reader.read_csv_chunked(columns=[lat_col, lon_col], max_chunks=100)
                    all_rows = []
                    for chunk in df_chunks:
                        all_rows.extend(chunk["rows"])

                    if all_rows:
                        df = pd.DataFrame(all_rows)
                        lat_series = pd.to_numeric(df[lat_col], errors="coerce")
                        lon_series = pd.to_numeric(df[lon_col], errors="coerce")

                        valid_lat = lat_series.between(-90, 90, inclusive="both")
                        valid_lon = lon_series.between(-180, 180, inclusive="both")
                        valid_mask = valid_lat & valid_lon

                        valid_count = int(valid_mask.sum())
                        invalid_count = len(valid_mask) - valid_count
                        total_records = len(valid_mask)

                        all_lats = lat_series[valid_mask].tolist()
                        all_lons = lon_series[valid_mask].tolist()
                except Exception:
                    total_records = 0
                    valid_count = 0
                    invalid_count = 0
            else:
                # No reader available - use profile data
                for col in [lat_col, lon_col]:
                    if col in self._profile.column_profiles:
                        cp = self._profile.column_profiles[col]
                        total_records += cp.null_count + cp.unique_count
                valid_count = 0
                invalid_count = total_records

        # Compute bounding box from valid coordinates
        bounding_box: Dict[str, float] = {
            "min_lat": None,
            "max_lat": None,
            "min_lon": None,
            "max_lon": None,
        }
        if all_lats and all_lons:
            try:
                bounding_box["min_lat"] = float(min(all_lats))
                bounding_box["max_lat"] = float(max(all_lats))
                bounding_box["min_lon"] = float(min(all_lons))
                bounding_box["max_lon"] = float(max(all_lons))
            except (ValueError, TypeError):
                pass

        # Compute coordinate distribution (buckets)
        distribution: Dict[str, Any] = {}
        if all_lats and all_lons and len(all_lats) > 0:
            try:
                n_buckets = min(10, len(all_lats))
                lat_bins = np.linspace(
                    bounding_box.get("min_lat", -90),
                    bounding_box.get("max_lat", 90),
                    n_buckets + 1,
                )
                lon_bins = np.linspace(
                    bounding_box.get("min_lon", -180),
                    bounding_box.get("max_lon", 180),
                    n_buckets + 1,
                )

                lat_indices = np.digitize(all_lats, lat_bins) - 1
                lon_indices = np.digitize(all_lons, lon_bins) - 1

                lat_labels = [
                    f"[{lat_bins[i]:.2f}, {lat_bins[i+1]:.2f})"
                    if i < n_buckets
                    else f"[{lat_bins[i]:.2f}, {lat_bins[i+1]:.2f}]"
                    for i in range(n_buckets + 1)
                ]
                lon_labels = [
                    f"[{lon_bins[i]:.2f}, {lon_bins[i+1]:.2f})"
                    if i < n_buckets
                    else f"[{lon_bins[i]:.2f}, {lon_bins[i+1]:.2f}]"
                    for i in range(n_buckets + 1)
                ]

                # Count cells
                cell_counts: Dict[str, int] = {}
                for la, lo, li, lj in zip(lat_indices, lon_indices, lat_labels, lon_labels):
                    key = f"{li}_{lj}"
                    cell_counts[key] = cell_counts.get(key, 0) + 1

                # Keep only non-empty cells
                distribution = {
                    k: v for k, v in cell_counts.items() if v > 0
                }
                # Limit to top 50 cells
                distribution = dict(sorted(distribution.items(), key=lambda x: x[1], reverse=True)[:50])
            except Exception:
                distribution = {}

        valid_percentage = (valid_count / total_records * 100) if total_records > 0 else 0.0

        source_cols: List[str] = []
        if lat_col:
            source_cols.append(lat_col)
        if lon_col:
            source_cols.append(lon_col)

        description = "Geographic coordinate validation and spatial distribution analysis"

        return GeospatialResult(
            valid_coordinate_count=valid_count,
            invalid_coordinate_count=invalid_count,
            total_records=total_records,
            bounding_box=bounding_box,
            coordinate_distribution=distribution,
            valid_percentage=round(valid_percentage, 2),
            source_columns=source_cols,
            calculation_basis=description,
        )

    def _compute_origin_destination_geographic(self) -> Optional[OriginDestinationSummary]:
        """Compute origin/destination geographic summaries when Origin/Destination fields exist."""
        origin_cols = self._get_role_columns(SemanticRole.ORIGIN)
        dest_cols = self._get_role_columns(SemanticRole.DESTINATION)

        available_origin = [c for c in origin_cols if c in self._profile.column_profiles]
        available_dest = [c for c in dest_cols if c in self._profile.column_profiles]

        if not available_origin and not available_dest:
            return None

        source_cols: List[str] = []
        origin_dist: Dict[str, Any] = {}
        dest_dist: Dict[str, Any] = {}

        # Unique origins/destinations count
        unique_origins = 0
        unique_destinations = 0

        if available_origin:
            try:
                reader = self._get_reader()
                od_col = available_origin[0]
                df_chunks = reader.read_csv_chunked(columns=[od_col], max_chunks=100)
                all_rows = []
                for chunk in df_chunks:
                    all_rows.extend(chunk["rows"])
                if all_rows:
                    df = pd.DataFrame(all_rows)
                    unique_origins = int(df[od_col].nunique())
                    source_cols.append(od_col)
            except Exception:
                col_profile = self._profile.column_profiles.get(available_origin[0], type('', (), {'unique_count': 0})())
                unique_origins = col_profile.unique_count if hasattr(col_profile, 'unique_count') else 0

        if available_dest:
            try:
                reader = self._get_reader()
                dest_col = available_dest[0]
                df_chunks = reader.read_csv_chunked(columns=[dest_col], max_chunks=100)
                all_rows = []
                for chunk in df_chunks:
                    all_rows.extend(chunk["rows"])
                if all_rows:
                    df = pd.DataFrame(all_rows)
                    unique_destinations = int(df[dest_col].nunique())
                    source_cols.append(dest_col)
            except Exception:
                col_profile = self._profile.column_profiles.get(available_dest[0], type('', (), {'unique_count': 0})())
                unique_destinations = col_profile.unique_count if hasattr(col_profile, 'unique_count') else 0

        description = "Origin/destination geographic summaries where origin/destination fields exist"

        return OriginDestinationSummary(
            unique_origins=unique_origins,
            unique_destinations=unique_destinations,
            unique_routes=0,
            origin_distribution=origin_dist,
            destination_distribution=dest_dist,
            source_columns=source_cols,
            calculation_basis=description,
        )


def create_geospatial_engine(
    profile: DatasetProfile,
    schema_intelligence: SchemaIntelligence | None = None,
    reader_provider: Optional[callable] | None = None,
) -> GeospatialEngine:
    return GeospatialEngine(profile, schema_intelligence, reader_provider)