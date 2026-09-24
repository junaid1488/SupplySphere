from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from dataset_analyzer.models import (
    DatasetProfile,
    ColumnProfile,
    SemanticRole,
    SchemaIntelligence,
    CapabilityDetection,
)


@dataclass(frozen=True)
class RouteResult:
    unique_origins: int
    unique_destinations: int
    unique_routes: int
    top_routes: List[Dict[str, Any]]
    route_frequency: Dict[str, int]
    origin_distribution: Dict[str, Any]
    destination_distribution: Dict[str, Any]
    route_volume: Optional[float]
    source_columns: List[str]
    calculation_basis: str
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unique_origins": self.unique_origins,
            "unique_destinations": self.unique_destinations,
            "unique_routes": self.unique_routes,
            "top_routes": self.top_routes,
            "route_frequency": self.route_frequency,
            "origin_distribution": self.origin_distribution,
            "destination_distribution": self.destination_distribution,
            "route_volume": self.route_volume,
            "source_columns": self.source_columns,
            "calculation_basis": self.calculation_basis,
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class RouteAnalysisReport:
    dataset_id: str
    routes: RouteResult
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "routes": self.routes.to_dict(),
            "computed_at": self.computed_at.isoformat(),
        }


class RouteEngine:
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

    def _get_role_columns(self, role: SemanticRole) -> List[str]:
        if not self._schema:
            return []
        role_cols: List[str] = []
        for detection in self._schema.detected_roles:
            if detection.role == role:
                role_cols.extend(detection.source_columns)
        return role_cols

    def compute_all(self) -> RouteAnalysisReport:
        origin_cols = self._get_role_columns(SemanticRole.ORIGIN)
        dest_cols = self._get_role_columns(SemanticRole.DESTINATION)

        available_origin = [c for c in origin_cols if c in self._profile.column_profiles]
        available_dest = [c for c in dest_cols if c in self._profile.column_profiles]

        # Compute route analysis only when origin + destination fields exist
        if not available_origin and not available_dest:
            # Return unavailable result
            unavailable_result = RouteResult(
                unique_origins=0,
                unique_destinations=0,
                unique_routes=0,
                top_routes=[],
                route_frequency={},
                origin_distribution={},
                destination_distribution={},
                route_volume=None,
                source_columns=[],
                calculation_basis="No origin or destination fields detected in dataset schema",
                limitations=["No origin or destination columns found"],
            )
            return RouteAnalysisReport(
                dataset_id=self._profile.dataset_id,
                routes=unavailable_result,
            )

        # Compute unique origins and destinations
        unique_origins = 0
        unique_destinations = 0
        unique_routes = 0
        origin_dist: Dict[str, Any] = {}
        dest_dist: Dict[str, Any] = {}
        route_frequency: Dict[str, int] = {}
        top_routes: List[Dict[str, Any]] = []
        source_cols: List[str] = []
        route_volume: Optional[float] = 0.0

        reader = self._get_reader()

        # Read origin/destination pairs
        if reader and available_origin and available_dest:
            try:
                od_col = available_origin[0]
                dest_col = available_dest[0]
                df_chunks = reader.read_csv_chunked(
                    columns=[od_col, dest_col], max_chunks=100
                )
                all_rows = []
                for chunk in df_chunks:
                    all_rows.extend(chunk["rows"])

                if all_rows:
                    df = pd.DataFrame(all_rows)
                    od_col_profile = self._profile.column_profiles.get(od_col)
                    dest_col_profile = self._profile.column_profiles.get(dest_col)

                    # Unique origins
                    unique_origins = int(df[od_col].nunique())
                    unique_destinations = int(df[dest_col].nunique())
                    source_cols = [od_col, dest_col]

                    # Unique routes (distinct origin-destination pairs)
                    pairs = set()
                    for _, row in df.iterrows():
                        o = row.get(od_col)
                        d = row.get(dest_col)
                        if o is not None and d is not None:
                            pairs.add((str(o), str(d)))
                    unique_routes = len(pairs)

                    # Route frequency (count of each route)
                    route_counts: Dict[str, int] = {}
                    for _, row in df.iterrows():
                        o = str(row.get(od_col, ""))
                        d = str(row.get(dest_col, ""))
                        key = f"{o} -> {d}"
                        route_counts[key] = route_counts.get(key, 0) + 1

                    # Top routes (top 10 by frequency)
                    sorted_routes = sorted(route_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                    for route, count in sorted_routes:
                        top_routes.append({"route": route, "frequency": count})

                    # Route frequency summary
                    route_frequency = dict(sorted(route_counts.items(), key=lambda x: x[1], reverse=True))

                    # Origin distribution
                    if od_col_profile:
                        origin_dist = {
                            cat: count
                            for cat, count in od_col_profile.categorical_summary.items()
                        } if od_col_profile.categorical_summary else {}

                    # Destination distribution
                    if dest_col_profile:
                        dest_dist = {
                            cat: count
                            for cat, count in dest_col_profile.categorical_summary.items()
                        } if dest_col_profile.categorical_summary else {}

                    # Route volume (total number of routed records)
                    route_volume = float(len(df))
                else:
                    route_volume = 0.0
            except Exception:
                unique_origins = 0
                unique_destinations = 0
                unique_routes = 0
                top_routes = []
                route_frequency = {}
                origin_dist = {}
                dest_dist = {}
                route_volume = 0.0
                source_cols = []
        else:
            # Only origin or only destination - compute what's available
            if available_origin and not available_dest:
                od_col = available_origin[0]
                try:
                    reader = self._get_reader()
                    if reader:
                        df_chunks = reader.read_csv_chunked(columns=[od_col], max_chunks=100)
                        all_rows = []
                        for chunk in df_chunks:
                            all_rows.extend(chunk["rows"])
                        if all_rows:
                            df = pd.DataFrame(all_rows)
                            unique_origins = int(df[od_col].nunique())
                            source_cols = [od_col]
                except Exception:
                    unique_origins = 0
            elif available_dest and not available_origin:
                dest_col = available_dest[0]
                try:
                    reader = self._get_reader()
                    if reader:
                        df_chunks = reader.read_csv_chunked(columns=[dest_col], max_chunks=100)
                        all_rows = []
                        for chunk in df_chunks:
                            all_rows.extend(chunk["rows"])
                        if all_rows:
                            df = pd.DataFrame(all_rows)
                            unique_destinations = int(df[dest_col].nunique())
                            source_cols = [dest_col]
                except Exception:
                    unique_destinations = 0

        description = "Route/origin-destination analysis where origin and destination fields exist"

        result = RouteResult(
            unique_origins=unique_origins,
            unique_destinations=unique_destinations,
            unique_routes=unique_routes,
            top_routes=top_routes,
            route_frequency=route_frequency,
            origin_distribution=origin_dist,
            destination_distribution=dest_dist,
            route_volume=route_volume,
            source_columns=source_cols,
            calculation_basis=description,
            limitations=[],  # Will be populated if needed
        )

        return RouteAnalysisReport(
            dataset_id=self._profile.dataset_id,
            routes=result,
        )


def create_route_engine(
    profile: DatasetProfile,
    schema_intelligence: SchemaIntelligence | None = None,
    reader_provider: Optional[callable] | None = None,
) -> RouteEngine:
    return RouteEngine(profile, schema_intelligence, reader_provider)