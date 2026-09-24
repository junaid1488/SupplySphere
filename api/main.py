from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from configs.settings import settings
from api.routes import dashboard, operations, geospatial, tracking, realtime, mlops, insights, reports
from dataset_analyzer import router as dataset_analyzer_router

app = FastAPI(title='SupplySphere API', version='1.2.0', description='Supply-chain control tower APIs for phases 0-17')
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.include_router(dashboard.router)
app.include_router(operations.router)
app.include_router(geospatial.router)
app.include_router(tracking.router)
app.include_router(realtime.router)
app.include_router(mlops.router)
app.include_router(insights.router)
app.include_router(reports.router)
app.include_router(dataset_analyzer_router)


@app.get('/api/health')
def health():
    return {
        'status': 'ok',
        'environment': settings.app_env,
        'phases': '0-17',
        'api_version': '1.2.0',
        'components': ['api', 'realtime', 'mlops', 'dataset_analyzer'],
    }
