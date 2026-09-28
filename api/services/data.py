from __future__ import annotations
from pathlib import Path
import json
import threading
import pandas as pd
from configs.settings import settings

# Low-cardinality string columns in the multi-million-row runtime CSVs.
# Reading them as plain objects costs ~600-800 MB of RSS per file and pushes
# the Render 512 MiB instance over its limit; as categoricals the same frame
# costs 70-250 MB with identical values in API responses.
_STOCKOUT_DTYPES = {
    'warehouse_id': 'category',
    'product_id': 'category',
    'risk_level': 'category',
    'expected_stockout_date': 'category',
}
_INVENTORY_DTYPES = {'warehouse_id': 'category', 'product_id': 'category'}

# stockout_predictions.csv is a multi-million-row frame; re-reading it for
# every request re-parses the file and briefly doubles peak RSS on the 512 MiB
# Render instance. One frame is loaded per process (keyed by data root, so a
# different root still reads its own file) and shared by every caller. All
# consumers only take masks/slices/copies from it, so returning the same object
# keeps columns, dtypes and response bytes identical while holding a single copy.
_STOCKOUT_FRAMES: dict[Path, pd.DataFrame] = {}
_STOCKOUT_LOCK = threading.Lock()


def _match_mask(series: pd.Series, q: str) -> pd.Series:
    """Substring-match a column without lowering every row.

    ``series.astype(str).str.lower().str.contains(...)`` on the 3.16 M-row
    stockout frame allocates 700-1200 MB (three full lowered string buffers).
    Categorical columns keep their distinct values in ``.cat.categories``
    (32 k for product_id, 12 for warehouse_id), so the match runs on those
    and is mapped back with ``isin`` for a few MB.
    """
    if series.empty:
        return pd.Series(False, index=series.index)
    if isinstance(series.dtype, pd.CategoricalDtype):
        categories = series.cat.categories.astype(str)
        matched = categories.str.lower().str.contains(q, regex=False, na=False)
        if not bool(matched.any()):
            return pd.Series(False, index=series.index)
        return series.isin(categories[matched])
    return series.astype(str).str.lower().str.contains(q, regex=False, na=False)

class DataRepository:
    def __init__(self, root: Path | None = None): self.root=Path(root or settings.processed_data_dir)
    def _read(self,name,usecols=None,dtype=None):
        p=self.root/name
        if not p.exists(): return pd.DataFrame()
        kwargs={}
        if usecols is not None: kwargs['usecols']=usecols
        if dtype is not None: kwargs['dtype']=dtype
        try: return pd.read_csv(p,**kwargs)
        except ValueError:
            # A requested column/dtype is not in this file: fall back to the
            # original read so responses stay identical.
            return pd.read_csv(p)
    def json(self,name):
        p=self.root/name
        return json.loads(p.read_text()) if p.exists() else {}
    def stockout(self):
        key=self.root.resolve()
        frame=_STOCKOUT_FRAMES.get(key)
        if frame is not None: return frame
        with _STOCKOUT_LOCK:
            frame=_STOCKOUT_FRAMES.get(key)
            if frame is None:
                frame=self._read('stockout_predictions.csv',dtype=_STOCKOUT_DTYPES)
                # A missing/unreadable file is not cached, so the original
                # re-attempt-on-every-call behaviour stays for empty frames.
                if not frame.empty: _STOCKOUT_FRAMES[key]=frame
        return frame
    def suppliers(self): return self._read('supplier_intelligence.csv')
    def warehouses(self): return self._read('warehouses.csv')
    def inventory(self): return self._read('inventory_snapshots.csv',dtype=_INVENTORY_DTYPES)
    def delivery(self): return self._read('delivery_risk_predictions.csv')
    def forecast(self): return self._read('forecast_7d.csv') if (self.root/'forecast_7d.csv').exists() else pd.DataFrame()
    def demand(self): return self._read('daily_product_demand.csv')
    def transfers(self): return self._read('warehouse_transfer_recommendations.csv')
    def forecast_metrics(self) -> dict:
        import joblib

        path = Path("ml/models/demand_forecast.joblib")
        if not path.exists():
            return {}
        try:
            artifact = joblib.load(path)
        except Exception:
            return {}
        if not isinstance(artifact, dict):
            return {}
        evaluation = artifact.get("evaluation", {})
        selected_model = artifact.get("selected_model")
        if not isinstance(evaluation, dict) or not selected_model:
            return {}
        metrics = evaluation.get(selected_model, {})
        if not isinstance(metrics, dict):
            return {}
        wape = metrics.get("WAPE")
        if wape is None:
            return {
                "selected_model": selected_model,
                "metrics": metrics,
            }
        return {
            "selected_model": selected_model,
            "wape": float(wape),
            "smape": float(metrics["sMAPE"]) if metrics.get("sMAPE") is not None else None,
            "mae": float(metrics["MAE"]) if metrics.get("MAE") is not None else None,
            "rmse": float(metrics["RMSE"]) if metrics.get("RMSE") is not None else None,
            "accuracy": float(max(0.0, 1.0 - float(wape))),
        }
    def optimization(self):
        x=self.json('phase10_summary.json')
        if not isinstance(x, dict):
            return {}
        return {
            'solver': x.get('solver'),
            'status': x.get('status'),
            'current_cost': x.get('current_cost'),
            'optimized_cost': x.get('optimized_cost'),
            'estimated_savings': x.get('estimated_savings'),
            'service_level': x.get('service_level'),
            'stockout_risk': x.get('stockout_risk'),
            'supplier_rows': x.get('supplier_rows'),
            'warehouse_rows': x.get('warehouse_rows'),
            'transfer_rows': x.get('transfer_rows'),
            'supplier_count': x.get('supplier_count'),
            'warehouse_count': x.get('warehouse_count'),
            'demand_rows': x.get('demand_rows'),
            'inventory_rows': x.get('inventory_rows'),
            'demand_snapshot_date': x.get('demand_snapshot_date'),
            'time_limit_ms': x.get('time_limit_ms'),
        }
    def search(self, q: str):
        q=q.lower().strip(); out=[]
        # stockout_predictions.csv must be read with the categorical dtypes:
        # as plain objects the three columns materialise ~900 MB of lowered
        # copies inside _match_mask, which OOMs the 512 MiB Render instance.
        for name,kind,cols,usecols,dtypes in [('stockout_predictions.csv','SKU',['product_id','warehouse_id','risk_level'],['product_id','warehouse_id','risk_level'],_STOCKOUT_DTYPES),('supplier_intelligence.csv','Supplier',['supplier_id','supplier_name','risk_level'],['supplier_id','supplier_name','risk_level'],None),('warehouses.csv','Warehouse',['warehouse_id','city'],['warehouse_id','city'],None),('delivery_risk_predictions.csv','Shipment',['order_id','risk_level'],['order_id','risk_level'],None)]:
            dtype={k:v for k,v in dtypes.items() if k in usecols} if dtypes else None
            df=self._read(name,usecols=usecols,dtype=dtype)
            if df.empty: continue
            mask=pd.Series(False,index=df.index)
            for c in cols:
                if c in df: mask |= _match_mask(df[c],q)
            for r in df[mask].head(20).to_dict('records'):
                rid=str(r.get(cols[0],'')); out.append({'type':kind,'id':rid,'label':rid,'status':r.get('status'),'risk_level':r.get('risk_level')})
        return out
