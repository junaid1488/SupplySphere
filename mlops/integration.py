from __future__ import annotations

def mlflow_available()->bool:
    try: import mlflow; return True
    except ImportError: return False

def evidently_available()->bool:
    try: import evidently; return True
    except ImportError: return False

def log_model_to_mlflow(*args,**kwargs):
    try:
        import mlflow
    except ImportError:
        return {'status':'unavailable','reason':'mlflow not installed'}
    return {'status':'available','mlflow_version':mlflow.__version__}
