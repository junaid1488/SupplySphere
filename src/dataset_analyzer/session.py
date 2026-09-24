from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from dataset_analyzer.models import DatasetMetadata, DatasetSession, DatasetStatus
from dataset_analyzer.storage import DatasetStorage, PathSafetyError, StorageError
from dataset_analyzer.reader import DatasetReader, ReaderError, create_reader
from dataset_analyzer.profiler import create_profiler, DatasetProfiler
from dataset_analyzer.schema_intelligence import create_schema_intelligence_analyzer, SchemaIntelligenceAnalyzer
from dataset_analyzer.capability_detection import create_capability_detector, CapabilityDetector
from dataset_analyzer.models import DatasetProfile, SchemaIntelligence, CapabilityDetection, FileFormat
from dataset_analyzer.kpi_engine import create_kpi_engine, KPIEngine, KPIReport
from dataset_analyzer.analytics_engine import create_analytics_engine, AnalyticsEngine, AnalyticsReport
from dataset_analyzer.trend_engine import create_trend_engine, TrendEngine, TrendReport
from dataset_analyzer.domain_engine import create_domain_engine, DomainEngine, DomainAnalysisReport
from dataset_analyzer.geospatial_engine import create_geospatial_engine, GeospatialEngine, GeospatialAnalysisReport
from dataset_analyzer.route_engine import create_route_engine, RouteEngine, RouteAnalysisReport
from dataset_analyzer.anomaly_engine import create_anomaly_engine, AnomalyEngine, AnomalyDetectionReport
from dataset_analyzer.query_engine import create_query_engine, QueryEngine, QueryAnalysisReport, QueryResult
from dataset_analyzer.insights_engine import create_insights_engine, InsightsEngine, InsightsReport, InsightResult
from dataset_analyzer.report_engine import create_report_engine, ReportEngine, ComprehensiveReport


class SessionError(Exception):
    pass


class SessionNotFoundError(SessionError):
    pass


class SessionExpiredError(SessionError):
    pass


class ReaderSessionError(SessionError):
    pass


class ProfilingError(SessionError):
    pass


class KPIError(SessionError):
    pass


class AnalyticsError(SessionError):
    pass


class TrendError(SessionError):
    pass


class DomainError(SessionError):
    pass


class GeospatialError(SessionError):
    pass


class RouteError(SessionError):
    pass


class AnomalyError(SessionError):
    pass


@dataclass
class SessionManager:
    storage: DatasetStorage
    max_file_size: int = 500 * 1024 * 1024
    _computation_cache: dict[str, dict] = field(default_factory=dict)
    _profile_locks: dict[str, Lock] = field(default_factory=dict)
    _profile_locks_guard: Lock = field(default_factory=Lock)

    def _get_profile_lock(self, dataset_id: str) -> Lock:
        with self._profile_locks_guard:
            if dataset_id not in self._profile_locks:
                self._profile_locks[dataset_id] = Lock()
            return self._profile_locks[dataset_id]

    def create_session(
        self,
        original_filename: str,
        file_obj: Any,
        file_size: int | None = None,
    ) -> DatasetSession:
        if file_size is not None and file_size > self.max_file_size:
            raise SessionError(f"File size {file_size} exceeds maximum {self.max_file_size}")

        try:
            session = self.storage.create_session(original_filename, file_obj, file_size)
            return session
        except (StorageError, PathSafetyError) as e:
            raise SessionError(f"Failed to create session: {e}") from e

    def get_session(self, dataset_id: str) -> DatasetSession:
        try:
            session = self.storage.get_session(dataset_id)
        except PathSafetyError as e:
            raise SessionError(f"Invalid dataset_id: {e}") from e

        if session is None:
            raise SessionNotFoundError(f"Dataset not found: {dataset_id}")

        if datetime.utcnow() > session.metadata.expires_at:
            raise SessionExpiredError(f"Dataset session expired: {dataset_id}")

        return session

    def get_metadata(self, dataset_id: str) -> DatasetMetadata:
        session = self.get_session(dataset_id)
        return session.metadata

    def update_status(self, dataset_id: str, status: DatasetStatus, error_message: str | None = None) -> DatasetMetadata:
        updates = {"status": status.value}
        if error_message is not None:
            updates["error_message"] = error_message
        return self.storage.update_metadata(dataset_id, **updates)

    def update_profile(
        self,
        dataset_id: str,
        row_count: int,
        column_count: int,
        column_names: list[str],
        column_types: dict[str, str],
    ) -> DatasetMetadata:
        return self.storage.update_metadata(
            dataset_id,
            status=DatasetStatus.READY.value,
            row_count=row_count,
            column_count=column_count,
            column_names=column_names,
            column_types=column_types,
        )

    def delete_session(self, dataset_id: str) -> bool:
        self._computation_cache.pop(dataset_id, None)
        with self._profile_locks_guard:
            self._profile_locks.pop(dataset_id, None)
        try:
            return self.storage.delete_session(dataset_id)
        except PathSafetyError as e:
            raise SessionError(f"Invalid dataset_id: {e}") from e

    def list_sessions(self) -> list[DatasetMetadata]:
        return self.storage.list_sessions()

    def cleanup_expired(self) -> int:
        return self.storage.cleanup_expired()

    def get_storage_path(self, dataset_id: str) -> Path:
        session = self.get_session(dataset_id)
        return session.storage_path

    def get_reader(self, dataset_id: str) -> DatasetReader:
        session = self.get_session(dataset_id)
        return create_reader(session)

    def preview_dataset(
        self,
        dataset_id: str,
        n_rows: int = 50,
        columns: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            reader = self.get_reader(dataset_id)
            return reader.get_preview(n_rows=n_rows, columns=columns)
        except ReaderError as e:
            raise ReaderSessionError(f"Preview failed: {e}") from e

    def sample_dataset(
        self,
        dataset_id: str,
        n_rows: int = 100,
        columns: list[str] | None = None,
        random_state: int | None = 42,
    ) -> dict[str, Any]:
        try:
            reader = self.get_reader(dataset_id)
            return reader.get_sample(n_rows=n_rows, columns=columns, random_state=random_state)
        except ReaderError as e:
            raise ReaderSessionError(f"Sampling failed: {e}") from e

    def list_sheets(self, dataset_id: str) -> list[str]:
        try:
            reader = self.get_reader(dataset_id)
            return reader.get_sheet_names()
        except ReaderError as e:
            raise ReaderSessionError(f"List sheets failed: {e}") from e

    def read_sheet(
        self,
        dataset_id: str,
        sheet_name: str | int = 0,
        n_rows: int | None = None,
        columns: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            reader = self.get_reader(dataset_id)
            return reader.read_sheet(sheet_name=sheet_name, n_rows=n_rows, columns=columns)
        except ReaderError as e:
            raise ReaderSessionError(f"Read sheet failed: {e}") from e

    def read_csv_chunks(
        self,
        dataset_id: str,
        chunk_size: int = 10_000,
        columns: list[str] | None = None,
        max_chunks: int | None = None,
    ) -> list[dict[str, Any]]:
        try:
            reader = self.get_reader(dataset_id)
            return reader.read_csv_chunked(chunk_size=chunk_size, columns=columns, max_chunks=max_chunks)
        except ReaderError as e:
            raise ReaderSessionError(f"Chunked read failed: {e}") from e

    def get_column_info(self, dataset_id: str) -> dict[str, Any]:
        try:
            reader = self.get_reader(dataset_id)
            return reader.get_column_info()
        except ReaderError as e:
            raise ReaderSessionError(f"Get column info failed: {e}") from e

    def get_row_count(self, dataset_id: str) -> int:
        try:
            reader = self.get_reader(dataset_id)
            return reader.get_row_count()
        except ReaderError as e:
            raise ReaderSessionError(f"Get row count failed: {e}") from e

    def profile_dataset(self, dataset_id: str) -> DatasetProfile:
        cached = self._computation_cache.get(dataset_id)
        if cached and "profile" in cached:
            return cached["profile"]

        lock = self._get_profile_lock(dataset_id)
        with lock:
            cached = self._computation_cache.get(dataset_id)
            if cached and "profile" in cached:
                return cached["profile"]

            try:
                session = self.get_session(dataset_id)
                profiler = create_profiler(session.storage_path, session.metadata.file_format)
                profile = profiler.profile()

                self.storage.update_metadata(
                    dataset_id,
                    status=DatasetStatus.READY.value,
                    row_count=profile.row_count,
                    column_count=profile.column_count,
                    column_names=profile.column_names,
                    column_types={col: prof.inferred_type.value for col, prof in profile.column_profiles.items()},
                )

                if dataset_id not in self._computation_cache:
                    self._computation_cache[dataset_id] = {}
                self._computation_cache[dataset_id]["profile"] = profile
                return profile
            except Exception as e:
                try:
                    self.update_status(dataset_id, DatasetStatus.ERROR, str(e))
                except Exception:
                    pass
                raise ProfilingError(f"Profiling failed: {e}") from e

    def analyze_schema(self, dataset_id: str) -> SchemaIntelligence:
        cached = self._computation_cache.get(dataset_id)
        if cached and "schema" in cached:
            return cached["schema"]
        try:
            profile = self.profile_dataset(dataset_id)
            analyzer = create_schema_intelligence_analyzer(profile)
            result = analyzer.analyze()
            if dataset_id not in self._computation_cache:
                self._computation_cache[dataset_id] = {}
            self._computation_cache[dataset_id]["schema"] = result
            return result
        except ProfilingError:
            raise
        except Exception as e:
            raise ProfilingError(f"Schema analysis failed: {e}") from e

    def detect_capabilities(self, dataset_id: str) -> CapabilityDetection:
        cached = self._computation_cache.get(dataset_id)
        if cached and "capabilities" in cached:
            return cached["capabilities"]
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            detector = create_capability_detector(profile, schema_intelligence)
            result = detector.detect_all()
            if dataset_id not in self._computation_cache:
                self._computation_cache[dataset_id] = {}
            self._computation_cache[dataset_id]["capabilities"] = result
            return result
        except ProfilingError:
            raise
        except Exception as e:
            raise ProfilingError(f"Capability detection failed: {e}") from e

    def compute_kpis(self, dataset_id: str) -> KPIReport:
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            capability_detection = self.detect_capabilities(dataset_id)
            engine = create_kpi_engine(
                profile,
                schema_intelligence,
                capability_detection,
                reader_provider=lambda: self.get_reader(dataset_id),
            )
            return engine.compute_all()
        except ProfilingError:
            raise
        except Exception as e:
            raise KPIError(f"KPI computation failed: {e}") from e

    def compute_analytics(self, dataset_id: str) -> AnalyticsReport:
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            engine = create_analytics_engine(
                profile,
                schema_intelligence,
                reader_provider=lambda: self.get_reader(dataset_id),
            )
            return engine.compute_all()
        except ProfilingError:
            raise
        except Exception as e:
            raise AnalyticsError(f"Analytics computation failed: {e}") from e

    def compute_trends(self, dataset_id: str) -> TrendReport:
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            engine = create_trend_engine(
                profile,
                schema_intelligence,
                reader_provider=lambda: self.get_reader(dataset_id),
            )
            return engine.compute_all()
        except ProfilingError:
            raise
        except Exception as e:
            raise TrendError(f"Trend computation failed: {e}") from e

    def compute_queries(self, dataset_id: str) -> QueryAnalysisReport:
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            engine = create_query_engine(
                profile,
                schema_intelligence,
                reader_provider=lambda: self.get_reader(dataset_id),
            )
            return engine.compute_all()
        except ProfilingError:
            raise
        except Exception as e:
            raise ProfilingError(f"Query computation failed: {e}") from e

    def compute_insights(self, dataset_id: str) -> InsightsReport:
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            capability_detection = self.detect_capabilities(dataset_id)
            engine = create_insights_engine(
                profile,
                schema_intelligence,
                capability_detection,
                reader_provider=lambda: self.get_reader(dataset_id),
            )
            return engine.compute_all()
        except ProfilingError:
            raise
        except Exception as e:
            raise ProfilingError(f"Insights computation failed: {e}") from e

    def compute_report(self, dataset_id: str) -> ComprehensiveReport:
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            capability_detection = self.detect_capabilities(dataset_id)
            engine = create_report_engine(
                profile,
                schema_intelligence,
                capability_detection,
                reader_provider=lambda: self.get_reader(dataset_id),
            )
            return engine.compute_all()
        except ProfilingError:
            raise
        except Exception as e:
            raise ProfilingError(f"Report computation failed: {e}") from e

    def compute_domain(self, dataset_id: str) -> DomainAnalysisReport:
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            capability_detection = self.detect_capabilities(dataset_id)
            engine = create_domain_engine(
                profile,
                schema_intelligence,
                capability_detection,
                reader_provider=lambda: self.get_reader(dataset_id),
            )
            return engine.compute_all()
        except ProfilingError:
            raise
        except Exception as e:
            raise DomainError(f"Domain computation failed: {e}") from e

    def compute_geospatial(self, dataset_id: str) -> GeospatialAnalysisReport:
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            engine = create_geospatial_engine(
                profile,
                schema_intelligence,
                reader_provider=lambda: self.get_reader(dataset_id),
            )
            return engine.compute_all()
        except ProfilingError:
            raise
        except Exception as e:
            raise GeospatialError(f"Geospatial computation failed: {e}") from e

    def compute_routes(self, dataset_id: str) -> RouteAnalysisReport:
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            engine = create_route_engine(
                profile,
                schema_intelligence,
                reader_provider=lambda: self.get_reader(dataset_id),
            )
            return engine.compute_all()
        except ProfilingError:
            raise
        except Exception as e:
            raise RouteError(f"Route computation failed: {e}") from e

    def compute_anomalies(self, dataset_id: str) -> AnomalyDetectionReport:
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            engine = create_anomaly_engine(
                profile,
                schema_intelligence,
                reader_provider=lambda: self.get_reader(dataset_id),
            )
            return engine.compute_all()
        except ProfilingError:
            raise
        except Exception as e:
            raise AnomalyError(f"Anomaly computation failed: {e}") from e

    def answer_question(self, dataset_id: str, question: str) -> QueryResult:
        try:
            profile = self.profile_dataset(dataset_id)
            schema_intelligence = self.analyze_schema(dataset_id)
            engine = create_query_engine(
                profile,
                schema_intelligence,
                reader_provider=lambda: self.get_reader(dataset_id),
            )
            return engine.answer_question(question)
        except ProfilingError:
            raise
        except Exception as e:
            raise ProfilingError(f"Query failed: {e}") from e