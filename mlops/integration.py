from __future__ import annotations

import importlib.util


def _installed(distribution: str) -> bool:
    """Report install status without importing the package.

    ``import mlflow``/``import evidently`` costs ~180 MB of RSS on first call,
    which is enough to push the Render Free 512 MiB instance over its limit
    the first time /api/mlops/health is hit. ``find_spec`` answers the same
    "is it installed" question without loading the library.
    """
    try:
        return importlib.util.find_spec(distribution) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def mlflow_available()->bool:
    return _installed('mlflow')

def evidently_available()->bool:
    return _installed('evidently')

def log_model_to_mlflow(*args,**kwargs):
    try:
        import mlflow
    except ImportError:
        return {'status':'unavailable','reason':'mlflow not installed'}
    return {'status':'available','mlflow_version':mlflow.__version__}
