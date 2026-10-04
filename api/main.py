import os
import threading
import time
from fastapi import FastAPI
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


def _warm_geospatial() -> None:
    """Pre-build every geospatial layer with the exact limit the map requests.
    The map fires ~10 layers at once; without this the burst of uncached builds
    queued behind the proxy timeout and spiked memory to the 512 MiB limit."""
    try:
        for net in ('brazil', 'india'):
            geospatial.warehouses(network=net, limit=500, offset=0)
            geospatial.transfers(network=net, limit=5000, offset=0)
            geospatial.routes(network=net)
        geospatial.sellers(limit=5000, offset=0)
        geospatial.shipping_lanes_endpoint(limit=2000, offset=0)
        geospatial.demand(limit=5000, offset=0)
        geospatial.inventory(limit=5000, offset=0)
        geospatial.orders(limit=5000, offset=0)
        geospatial.customers(limit=10000, offset=0)
        geospatial.delivery(limit=5000, offset=0)
        geospatial.orders(limit=10000, offset=0)
        geospatial.delivery(limit=10000, offset=0)
    except Exception:
        pass


def _warm_expensive_routes() -> None:
    """Compute the derived aggregates once, right after boot, so the first user
    request is not the one paying the multi-second streaming pass."""
    for step in (dashboard._warm_caches, insights.insights, reports.reports, _warm_geospatial):
        try:
            step()
        except Exception:
            pass
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
