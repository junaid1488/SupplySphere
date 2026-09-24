from fastapi import APIRouter, Query
from mlops.registry import ModelRegistry

router=APIRouter(prefix='/api/mlops',tags=['mlops']); registry=ModelRegistry()
@router.get('/models')
def models(name:str|None=None): return {'items':registry.list(name)}
@router.get('/health')
def health():
    from mlops.integration import mlflow_available,evidently_available
    return {'registry':'ok','mlflow_installed':mlflow_available(),'evidently_installed':evidently_available()}
