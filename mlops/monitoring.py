from __future__ import annotations
from dataclasses import asdict, dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class DriftMetric:
    feature: str
    baseline_mean: float
    current_mean: float
    mean_shift_pct: float
    drift: bool

def _shift(a,b):
    denom=max(abs(a),1e-9); return abs(b-a)/denom*100

def feature_drift(reference: pd.DataFrame,current: pd.DataFrame,threshold_pct: float=20.0)->list[DriftMetric]:
    out=[]
    for c in reference.select_dtypes(include=np.number).columns:
        if c not in current: continue
        a=float(reference[c].dropna().mean()); b=float(current[c].dropna().mean()); shift=_shift(a,b)
        out.append(DriftMetric(c,a,b,shift,shift>=threshold_pct))
    return out

def prediction_drift(reference: pd.Series,current: pd.Series,threshold_pct: float=20.0)->dict:
    a=float(reference.mean()); b=float(current.mean()); shift=_shift(a,b)
    return {'reference_mean':a,'current_mean':b,'mean_shift_pct':shift,'drift':shift>=threshold_pct}

def monitoring_report(reference:pd.DataFrame,current:pd.DataFrame,reference_predictions:pd.Series|None=None,current_predictions:pd.Series|None=None)->dict:
    features=[asdict(x) for x in feature_drift(reference,current)]
    report={'feature_drift':features,'drifted_features':sum(x['drift'] for x in features),'total_features':len(features)}
    if reference_predictions is not None and current_predictions is not None: report['prediction_drift']=prediction_drift(reference_predictions,current_predictions)
    return report
