from __future__ import annotations
import pandas as pd

def explain(model, X: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    X=X.copy()
    try:
        import shap
        explainer=shap.TreeExplainer(model)
        vals=explainer.shap_values(X)
        if isinstance(vals,list): vals=vals[-1]
        if getattr(vals,'ndim',0)==3: vals=vals[:,:,1]
        importance=pd.Series(abs(vals).mean(axis=0),index=X.columns).sort_values(ascending=False).head(top_n)
        return importance.rename('mean_abs_shap').reset_index().rename(columns={'index':'feature'})
    except Exception:
        importance=pd.Series(getattr(model,'feature_importances_',[]),index=X.columns).sort_values(ascending=False).head(top_n)
        return importance.rename('importance').reset_index().rename(columns={'index':'feature'})
