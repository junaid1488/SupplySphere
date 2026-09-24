from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from dataset_analyzer.models import (
    DatasetProfile,
    SchemaIntelligence,
    CapabilityDetection,
)
from dataset_analyzer.kpi_engine import KPIReport, create_kpi_engine
from dataset_analyzer.analytics_engine import AnalyticsReport, create_analytics_engine
from dataset_analyzer.trend_engine import TrendReport, create_trend_engine
from dataset_analyzer.domain_engine import DomainAnalysisReport, create_domain_engine
from dataset_analyzer.geospatial_engine import GeospatialAnalysisReport, create_geospatial_engine
from dataset_analyzer.route_engine import RouteAnalysisReport, create_route_engine
from dataset_analyzer.anomaly_engine import AnomalyDetectionReport, create_anomaly_engine
from dataset_analyzer.query_engine import QueryAnalysisReport, create_query_engine
from dataset_analyzer.insights_engine import InsightsReport, create_insights_engine


@dataclass(frozen=True)
class ComprehensiveReport:
    dataset_id: str
    dataset_summary: Dict[str, Any]
    kpis: Optional[KPIReport]
    analytics: Optional[AnalyticsReport]
    trends: Optional[TrendReport]
    domain: Optional[DomainAnalysisReport]
    geospatial: Optional[GeospatialAnalysisReport]
    routes: Optional[RouteAnalysisReport]
    anomalies: Optional[AnomalyDetectionReport]
    queries: Optional[QueryAnalysisReport]
    insights: Optional[InsightsReport]
    unavailable: Dict[str, str]
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        result: Dict[str, Any] = {
            "dataset_id": self.dataset_id,
            "dataset_summary": self.dataset_summary,
            "computed_at": self.computed_at.isoformat(),
            "unavailable": self.unavailable,
        }
        if self.kpis is not None:
            result["kpis"] = self.kpis.to_dict()
        if self.analytics is not None:
            result["analytics"] = self.analytics.to_dict()
        if self.trends is not None:
            result["trends"] = self.trends.to_dict()
        if self.domain is not None:
            result["domain"] = self.domain.to_dict()
        if self.geospatial is not None:
            result["geospatial"] = self.geospatial.to_dict()
        if self.routes is not None:
            result["routes"] = self.routes.to_dict()
        if self.anomalies is not None:
            result["anomalies"] = self.anomalies.to_dict()
        if self.queries is not None:
            result["queries"] = self.queries.to_dict()
        if self.insights is not None:
            result["insights"] = self.insights.to_dict()
        return result


class ReportEngine:
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

    def _get_reader(self) -> Optional[object]:
        if self._reader_provider:
            try:
                return self._reader_provider()
            except Exception:
                pass
        return None

    def _compute_dataset_summary(self) -> Dict[str, Any]:
        total_cells = self._profile.row_count * self._profile.column_count
        total_nulls = sum(cp.null_count for cp in self._profile.column_profiles.values())
        missing_rate = (total_nulls / total_cells * 100) if total_cells > 0 else 0.0

        dup_rate = 0.0
        if self._profile.duplicate_row_count >= 0 and self._profile.row_count > 0:
            dup_rate = (self._profile.duplicate_row_count / self._profile.row_count * 100)

        return {
            "row_count": self._profile.row_count,
            "column_count": self._profile.column_count,
            "column_names": self._profile.column_names,
            "numeric_columns": self._profile.numeric_columns,
            "categorical_columns": self._profile.categorical_columns,
            "datetime_columns": self._profile.datetime_columns,
            "missing_value_rate_pct": round(missing_rate, 2),
            "duplicate_row_count": self._profile.duplicate_row_count if self._profile.duplicate_row_count >= 0 else None,
            "duplicate_row_rate_pct": round(dup_rate, 2) if self._profile.duplicate_row_count >= 0 else None,
            "limitations": self._profile.limitations,
        }

    def compute_all(self) -> ComprehensiveReport:
        reader = self._get_reader()
        unavailable: Dict[str, str] = {}

        dataset_summary = self._compute_dataset_summary()

        kpis = None
        analytics = None
        trends = None
        domain = None
        geospatial = None
        routes = None
        anomalies = None
        queries = None
        insights = None

        try:
            kpi_engine = create_kpi_engine(
                self._profile,
                self._schema,
                self._capabilities,
                reader_provider=lambda: reader,
            )
            kpis = kpi_engine.compute_all()
        except Exception as e:
            unavailable["kpis"] = f"Computation failed: {str(e)}"

        try:
            analytics_engine = create_analytics_engine(
                self._profile,
                self._schema,
                reader_provider=lambda: reader,
            )
            analytics = analytics_engine.compute_all()
        except Exception as e:
            unavailable["analytics"] = f"Computation failed: {str(e)}"

        try:
            trend_engine = create_trend_engine(
                self._profile,
                self._schema,
                reader_provider=lambda: reader,
            )
            trends = trend_engine.compute_all()
        except Exception as e:
            unavailable["trends"] = f"Computation failed: {str(e)}"

        try:
            domain_engine = create_domain_engine(
                self._profile,
                self._schema,
                self._capabilities,
                reader_provider=lambda: reader,
            )
            domain = domain_engine.compute_all()
        except Exception as e:
            unavailable["domain"] = f"Computation failed: {str(e)}"

        try:
            geo_engine = create_geospatial_engine(
                self._profile,
                self._schema,
                reader_provider=lambda: reader,
            )
            geospatial = geo_engine.compute_all()
        except Exception as e:
            unavailable["geospatial"] = f"Computation failed: {str(e)}"

        try:
            route_engine = create_route_engine(
                self._profile,
                self._schema,
                reader_provider=lambda: reader,
            )
            routes = route_engine.compute_all()
        except Exception as e:
            unavailable["routes"] = f"Computation failed: {str(e)}"

        try:
            anomaly_engine = create_anomaly_engine(
                self._profile,
                self._schema,
                reader_provider=lambda: reader,
            )
            anomalies = anomaly_engine.compute_all()
        except Exception as e:
            unavailable["anomalies"] = f"Computation failed: {str(e)}"

        try:
            query_engine = create_query_engine(
                self._profile,
                self._schema,
                reader_provider=lambda: reader,
            )
            queries = query_engine.compute_all()
        except Exception as e:
            unavailable["queries"] = f"Computation failed: {str(e)}"

        try:
            insights_engine = create_insights_engine(
                self._profile,
                self._schema,
                self._capabilities,
                reader_provider=lambda: reader,
            )
            insights = insights_engine.compute_all()
        except Exception as e:
            unavailable["insights"] = f"Computation failed: {str(e)}"

        if self._capabilities:
            for cap in self._capabilities.capabilities:
                if cap.status.value == "unavailable" and cap.name not in unavailable:
                    unavailable[cap.name] = cap.reason or "Required fields not detected"

        return ComprehensiveReport(
            dataset_id=self._profile.dataset_id,
            dataset_summary=dataset_summary,
            kpis=kpis,
            analytics=analytics,
            trends=trends,
            domain=domain,
            geospatial=geospatial,
            routes=routes,
            anomalies=anomalies,
            queries=queries,
            insights=insights,
            unavailable=unavailable,
            computed_at=datetime.utcnow(),
        )


def create_report_engine(
    profile: DatasetProfile,
    schema_intelligence: SchemaIntelligence | None = None,
    capability_detection: CapabilityDetection | None = None,
    reader_provider: Optional[callable] | None = None,
) -> ReportEngine:
    return ReportEngine(profile, schema_intelligence, capability_detection, reader_provider)
