from __future__ import annotations
from pathlib import Path
import json
import pandas as pd
import joblib
from configs.settings import settings

class DataRepository:
    def __init__(self, root: Path | None = None): self.root=Path(root or settings.processed_data_dir)
    def _read(self,name):
        p=self.root/name
        return pd.read_csv(p) if p.exists() else pd.DataFrame()
    def json(self,name):
        p=self.root/name
        return json.loads(p.read_text()) if p.exists() else {}
    def stockout(self): return self._read('stockout_predictions.csv')
    def suppliers(self): return self._read('supplier_intelligence.csv')
    def warehouses(self): return self._read('warehouses.csv')
    def inventory(self): return self._read('inventory_snapshots.csv')
    def delivery(self): return self._read('delivery_risk_predictions.csv')
    def forecast(self): return self._read('forecast_7d.csv') if (self.root/'forecast_7d.csv').exists() else pd.DataFrame()
    def demand(self): return self._read('daily_product_demand.csv')
    def transfers(self): return self._read('warehouse_transfer_recommendations.csv')
    def forecast_metrics(self) -> dict:
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
        for name,kind,cols in [('stockout_predictions.csv','SKU',['product_id','warehouse_id','risk_level']),('supplier_intelligence.csv','Supplier',['supplier_id','supplier_name','risk_level']),('warehouses.csv','Warehouse',['warehouse_id','city']),('delivery_risk_predictions.csv','Shipment',['order_id','risk_level'])]:
            df=self._read(name)
            if df.empty: continue
            mask=pd.Series(False,index=df.index)
            for c in cols:
                if c in df: mask |= df[c].astype(str).str.lower().str.contains(q,regex=False,na=False)
            for r in df[mask].head(20).to_dict('records'):
                rid=str(r.get(cols[0],'')); out.append({'type':kind,'id':rid,'label':rid,'status':r.get('status'),'risk_level':r.get('risk_level')})
        return out
