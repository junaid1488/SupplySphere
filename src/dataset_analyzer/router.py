from __future__ import annotations
from fastapi import APIRouter, File, HTTPException, UploadFile, status, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTasks

from dataset_analyzer.models import DatasetStatus
from dataset_analyzer.session import (
    SessionManager,
    SessionError,
    SessionNotFoundError,
    SessionExpiredError,
    ReaderSessionError,
    ProfilingError,
    KPIError,
    AnalyticsError,
    TrendError,
    DomainError,
    GeospatialError,
    RouteError,
    AnomalyError,
)
from dataset_analyzer.storage import (
    DatasetStorage,
    ContentValidationError,
    FileSizeLimitError,
    EmptyFileError,
)
from dataset_analyzer.kpi_engine import KPIEngine, KPIReport, KPIResult, create_kpi_engine
from dataset_analyzer.analytics_engine import AnalyticsEngine, AnalyticsReport, AnalyticsResult, create_analytics_engine
from dataset_analyzer.trend_engine import TrendEngine, TrendReport, TrendResult, create_trend_engine
from dataset_analyzer.query_engine import QueryEngine, QueryAnalysisReport, QueryResult, create_query_engine
from dataset_analyzer.insights_engine import InsightsEngine, InsightsReport, InsightResult, create_insights_engine
from dataset_analyzer.report_engine import ReportEngine, ComprehensiveReport, create_report_engine

router = APIRouter(prefix="/api/dataset-analyzer", tags=["dataset-analyzer"])

_storage = DatasetStorage()
_manager = SessionManager(storage=_storage)


def _run_profiling(dataset_id: str) -> None:
    """Background task: profile dataset and transition status to ready/error."""
    try:
        _manager.profile_dataset(dataset_id)
    except Exception:
        try:
            _manager.update_status(dataset_id, DatasetStatus.ERROR, "Profiling failed")
        except Exception:
            pass


@router.post("/sessions", status_code=status.HTTP_201_CREATED, response_model=None)
async def create_session(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    allowed_extensions = {".csv", ".xls", ".xlsx"}
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed: {', '.join(allowed_extensions)}",
        )

    try:
        session = await run_in_threadpool(
            _manager.create_session, file.filename, file.file, file.size
        )
        await run_in_threadpool(
            _manager.update_status, session.dataset_id, DatasetStatus.PROCESSING
        )

        if background_tasks is not None:
            background_tasks.add_task(_run_profiling, session.dataset_id)

        refreshed = _manager.get_session(session.dataset_id)
        return JSONResponse(
            content={
                "dataset_id": refreshed.dataset_id,
                "status": refreshed.metadata.status.value,
                "original_filename": refreshed.metadata.original_filename,
                "file_size_bytes": refreshed.metadata.file_size_bytes,
                "created_at": refreshed.metadata.created_at.isoformat(),
                "expires_at": refreshed.metadata.expires_at.isoformat(),
            },
            status_code=status.HTTP_201_CREATED,
        )
    except FileSizeLimitError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except EmptyFileError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ContentValidationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid file content: {e}") from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}")
async def get_session(dataset_id: str):
    try:
        session = _manager.get_session(dataset_id)
        return session.metadata.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/sessions/{dataset_id}")
async def delete_session(dataset_id: str):
    try:
        deleted = _manager.delete_session(dataset_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")
        return {"deleted": True, "dataset_id": dataset_id}
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions")
async def list_sessions():
    sessions = _manager.list_sessions()
    return {"sessions": [s.to_dict() for s in sessions]}


@router.post("/sessions/{dataset_id}/cleanup")
async def cleanup_expired():
    count = _manager.cleanup_expired()
    return {"cleaned_up": count}


@router.get("/sessions/{dataset_id}/preview")
async def preview_dataset(
    dataset_id: str,
    n_rows: int = Query(50, ge=1, le=100),
    columns: str | None = Query(None, description="Comma-separated column names"),
):
    try:
        col_list = columns.split(",") if columns else None
        result = _manager.preview_dataset(dataset_id, n_rows=n_rows, columns=col_list)
        return result
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ReaderSessionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/sample")
async def sample_dataset(
    dataset_id: str,
    n_rows: int = Query(100, ge=1, le=1000),
    columns: str | None = Query(None, description="Comma-separated column names"),
    random_state: int | None = Query(42),
):
    try:
        col_list = columns.split(",") if columns else None
        result = _manager.sample_dataset(dataset_id, n_rows=n_rows, columns=col_list, random_state=random_state)
        return result
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ReaderSessionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/sheets")
async def list_sheets(dataset_id: str):
    try:
        sheets = _manager.list_sheets(dataset_id)
        return {"sheets": sheets}
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ReaderSessionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/sheets/{sheet_name}")
async def read_sheet(
    dataset_id: str,
    sheet_name: str,
    n_rows: int | None = Query(None, ge=1, le=1000),
    columns: str | None = Query(None, description="Comma-separated column names"),
):
    try:
        col_list = columns.split(",") if columns else None
        try:
            sheet_idx = int(sheet_name)
        except ValueError:
            sheet_idx = sheet_name
        result = _manager.read_sheet(dataset_id, sheet_name=sheet_idx, n_rows=n_rows, columns=col_list)
        return result
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ReaderSessionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/columns")
async def get_columns(dataset_id: str):
    try:
        result = _manager.get_column_info(dataset_id)
        return result
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ReaderSessionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/row-count")
async def get_row_count(dataset_id: str):
    try:
        count = _manager.get_row_count(dataset_id)
        return {"row_count": count}
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ReaderSessionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/sessions/{dataset_id}/read-chunked")
async def read_chunked(
    dataset_id: str,
    chunk_size: int = Query(10000, ge=100, le=50000),
    columns: str | None = Query(None, description="Comma-separated column names"),
    max_chunks: int | None = Query(None, ge=1, le=100),
):
    try:
        col_list = columns.split(",") if columns else None
        chunks = _manager.read_csv_chunks(dataset_id, chunk_size=chunk_size, columns=col_list, max_chunks=max_chunks)
        return {"chunks": chunks, "chunk_count": len(chunks)}
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ReaderSessionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/profile")
async def get_profile(dataset_id: str):
    try:
        profile = await run_in_threadpool(_manager.profile_dataset, dataset_id)
        return profile.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ProfilingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/schema")
async def get_schema_intelligence(dataset_id: str):
    try:
        schema = await run_in_threadpool(_manager.analyze_schema, dataset_id)
        return schema.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ProfilingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/capabilities")
async def get_capabilities(dataset_id: str):
    try:
        capabilities = await run_in_threadpool(_manager.detect_capabilities, dataset_id)
        return capabilities.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ProfilingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/kpis")
async def get_kpis(dataset_id: str):
    try:
        kpis = await run_in_threadpool(_manager.compute_kpis, dataset_id)
        return kpis.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except KPIError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/analytics")
async def get_analytics(dataset_id: str):
    try:
        analytics = await run_in_threadpool(_manager.compute_analytics, dataset_id)
        return analytics.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except AnalyticsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/trends")
async def get_trends(dataset_id: str):
    try:
        trends = await run_in_threadpool(_manager.compute_trends, dataset_id)
        return trends.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except TrendError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/queries")
async def get_queries(dataset_id: str):
    try:
        queries = await run_in_threadpool(_manager.compute_queries, dataset_id)
        return queries.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ProfilingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/insights")
async def get_insights(dataset_id: str):
    try:
        insights = await run_in_threadpool(_manager.compute_insights, dataset_id)
        return insights.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ProfilingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/report")
async def get_report(dataset_id: str):
    try:
        report = await run_in_threadpool(_manager.compute_report, dataset_id)
        return report.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ProfilingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/domain")
async def get_domain(dataset_id: str):
    try:
        result = await run_in_threadpool(_manager.compute_domain, dataset_id)
        return result.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/geospatial")
async def get_geospatial(dataset_id: str):
    try:
        result = await run_in_threadpool(_manager.compute_geospatial, dataset_id)
        return result.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except GeospatialError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/routes")
async def get_routes(dataset_id: str):
    try:
        result = await run_in_threadpool(_manager.compute_routes, dataset_id)
        return result.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except RouteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{dataset_id}/anomalies")
async def get_anomalies(dataset_id: str):
    try:
        result = await run_in_threadpool(_manager.compute_anomalies, dataset_id)
        return result.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except AnomalyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/sessions/{dataset_id}/ask")
async def ask_question(dataset_id: str, body: dict):
    question = body.get("question", "")
    if not question or not isinstance(question, str):
        raise HTTPException(status_code=400, detail="A non-empty 'question' string is required")
    try:
        result = await run_in_threadpool(_manager.answer_question, dataset_id, question)
        return result.to_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    except ProfilingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e