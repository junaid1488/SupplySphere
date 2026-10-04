import os
import threading
import time
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from configs.settings import settings
from api.routes import dashboard, operations, geospatial, tracking, realtime, mlops, insights, reports
from dataset_analyzer import router as dataset_analyzer_router

_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "https://supplysphere.vercel.app,http://localhost:5173").split(",") if o.strip()]

app = FastAPI(title='SupplySphere API', version='1.2.0', description='Supply-chain control tower APIs for phases 0-17')
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.include_router(dashboard.router)
app.include_router(operations.router)
app.include_router(geospatial.router)
app.include_router(tracking.router)
app.include_router(realtime.router)
app.include_router(mlops.router)
app.include_router(insights.router)
app.include_router(reports.router)
app.include_router(dataset_analyzer_router)


def _rss_mb() -> float:
    try:
        with open('/proc/self/statm') as fh:
            pages = int(fh.read().split()[1])
        return round(pages * os.sysconf('SC_PAGE_SIZE') / 1048576, 1)
    except Exception:
        return 0.0


_WARM_STATE = {'done': False}
_WARM_BUDGET_SECONDS = 60.0


@app.get('/api/health')
def health():
    return {
        'status': 'ok',
        'environment': settings.app_env,
        'phases': '0-17',
        'api_version': '1.2.0',
        'components': ['api', 'realtime', 'mlops', 'dataset_analyzer'],
        'rss_mb': _rss_mb(),
        'warm': _WARM_STATE['done'],
    }


@app.head('/api/health')
def health_head() -> Response:
    """UptimeRobot probes with HEAD; FastAPI registers GET-only routes, so HEAD
    was answering 405 Method Not Allowed and the monitor reported DOWN.
    Same 200 status as GET, empty body, no change to the GET payload."""
    return Response(status_code=200, media_type='application/json')


def _warm_geospatial(deadline: float) -> None:
    """Build only the layers the first map view asks for, and stop as soon as
    the boot budget runs out.

    Warming every layer at every limit the UI can request kept a dozen
    5-20 MiB payloads plus their 100k-row build frames alive at boot, pushed
    RSS past the 512 MiB limit and the worker was OOM-killed - that is what the
    site saw as 502s.  The heavier layers (orders/customers/delivery/demand/
    inventory) now build lazily on first request, two at a time
    (geospatial._BUILD_SLOTS), which is what their own payload cache is for."""
    steps = []
    for net in ('brazil', 'india'):
        steps.append(lambda net=net: geospatial.warehouses(network=net, limit=500, offset=0))
        steps.append(lambda net=net: geospatial.routes(network=net))
        steps.append(lambda net=net: geospatial.transfers(network=net, limit=5000, offset=0))
    steps.append(lambda: geospatial.sellers(limit=5000, offset=0))
    steps.append(lambda: geospatial.shipping_lanes_endpoint(limit=2000, offset=0))
    for step in steps:
        if time.monotonic() >= deadline:
            return
        try:
            step()
        except Exception:
            pass


def _warm_expensive_routes() -> None:
    """Compute the derived aggregates once, right after boot, so the first user
    request is not the one paying the multi-second streaming pass.

    The warm-up is bounded by _WARM_BUDGET_SECONDS and always reports warm
    afterwards: an unbounded warm-up held hundreds of MiB, OOM-killed the
    512 MiB worker and turned every request into a 502."""
    deadline = time.monotonic() + _WARM_BUDGET_SECONDS
    try:
        for step in (
            dashboard._warm_caches,
            lambda: _warm_geospatial(deadline),
            insights.insights,
            reports.reports,
        ):
            if time.monotonic() >= deadline:
                break
            try:
                step()
            except Exception:
                pass
    finally:
        _WARM_STATE['done'] = True


def _periodic_session_cleanup() -> None:
    """Expired analyzer sessions keep their cached reports in RAM; sweep every
    10 minutes so the 512 MiB worker cannot drift into an OOM 502."""
    while True:
        time.sleep(600)
        try:
            dataset_analyzer_router._manager.cleanup_expired()
        except Exception:
            pass


@app.on_event('startup')
def _schedule_warmup() -> None:
    threading.Thread(target=_warm_expensive_routes, daemon=True).start()
    threading.Thread(target=_periodic_session_cleanup, daemon=True).start()
