from __future__ import annotations
from collections import OrderedDict
from pathlib import Path
import gc
import json
import threading
import pandas as pd
from configs.settings import settings

_STOCKOUT_DTYPES = {
    'warehouse_id': 'category',
    'product_id': 'category',
    'risk_level': 'category',
    'expected_stockout_date': 'category',
}
_INVENTORY_DTYPES = {'warehouse_id': 'category', 'product_id': 'category'}

_SMALL_FRAME_CACHE: dict[tuple, pd.DataFrame] = {}
_SMALL_FRAME_LOCK = threading.Lock()

# Derived aggregates over the multi-hundred-MB CSVs.  They are computed by a
# streaming pass (~5-15 s) and are immutable for the life of the process, so
# every route (insights, reports, dashboard) shares one result.
_DERIVED_CACHE: dict[str, object] = {}
_DERIVED_LOCK = threading.Lock()

_STOCKOUT_CHUNKSIZE = 50_000
_INVENTORY_CHUNKS = 50_000

# /api/search bounds: 50 k row chunks with a gc every _SEARCH_GC_EVERY chunks
# (250 k rows) so chunk frames return to the OS, at most _SEARCH_MAX_RESULTS rows
# retained per source file, plus a tiny LRU of finished results.  Together these
# keep a full scan (~133 MB peak, measured) inside the Render Free 512 MiB budget.
_SEARCH_CHUNKSIZE = 50_000
_SEARCH_MAX_RESULTS = 20
_SEARCH_GC_EVERY = 5
_SEARCH_CACHE_MAX = 64
_SEARCH_CACHE: OrderedDict[str, list[dict]] = OrderedDict()
_SEARCH_CACHE_LOCK = threading.Lock()

# ml/stockout/model.py::risk_level() only ever returns one of these four
# strings, so the deployed code is a guaranteed superset of the values present
# in stockout_predictions.csv.  A superset can never cause a wrong skip, which
# makes risk_level pruning safe from the very first request after boot - no
# warm-up pass over the 293 MB file required.
_STOCKOUT_RISK_DOMAIN = ("Critical", "High", "Medium", "Low")

# product_id / warehouse_id domains come from these tiny files; a domain is
# only trusted when it is large enough to be a real catalog (the stockout file
# spans 32 951 products / 12 warehouses).
_PRODUCT_DOMAIN_MIN_PRODUCTS = 1_000


def _match_mask(series: pd.Series, q: str) -> pd.Series:
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
            return pd.read_csv(p)
    def json(self,name):
        p=self.root/name
        return json.loads(p.read_text()) if p.exists() else {}
    def _cached_small(self, key: tuple, name: str) -> pd.DataFrame:
        frame = _SMALL_FRAME_CACHE.get(key)
        if frame is not None:
            return frame
        with _SMALL_FRAME_LOCK:
            frame = _SMALL_FRAME_CACHE.get(key)
            if frame is None:
                frame = self._read(name)
                if not frame.empty:
                    _SMALL_FRAME_CACHE[key] = frame
        return frame
    def stockout(self):
        return self._read('stockout_predictions.csv', dtype=_STOCKOUT_DTYPES)
    def stockout_risk_totals(self) -> dict:
        """Row counts of High/Critical stockout risk without materialising the
        293 MB / 3.16 M row frame (a full read peaks well over the Render 512 MiB
        limit and gets the process OOM-killed -> 502 on every later request)."""
        cached = _DERIVED_CACHE.get('stockout_risk_totals')
        if cached is not None:
            return cached  # type: ignore[return-value]
        path = self.root / 'stockout_predictions.csv'
        empty = {"high": 0, "critical": 0, "total": 0}
        if not path.exists():
            return empty
        high = 0
        critical = 0
        total = 0
        levels: set[str] = set()
        with _DERIVED_LOCK:
            cached = _DERIVED_CACHE.get('stockout_risk_totals')
            if cached is not None:
                return cached  # type: ignore[return-value]
            try:
                for chunk in pd.read_csv(path, usecols=['risk_level'], chunksize=_STOCKOUT_CHUNKSIZE):
                    if 'risk_level' not in chunk.columns:
                        del chunk
                        continue
                    levels.update(str(v) for v in chunk['risk_level'].dropna().unique().tolist())
                    high += int(chunk['risk_level'].eq('High').sum())
                    critical += int(chunk['risk_level'].eq('Critical').sum())
                    total += len(chunk)
                    del chunk
                gc.collect()
            except Exception:
                return empty
            if levels:
                _DERIVED_CACHE['stockout_risk_levels'] = levels
            result = {"high": high, "critical": critical, "total": total}
            _DERIVED_CACHE['stockout_risk_totals'] = result
            return result
    def inventory_snapshot_stats(self) -> dict:
        """Latest-snapshot inventory stats computed in a single streaming pass
        over inventory_snapshots.csv (169 MB / 3.16 M rows) instead of loading
        the whole frame (which peaks past the Render 512 MiB limit)."""
        path = self.root / 'inventory_snapshots.csv'
        if not path.exists():
            return {}
        cached = _DERIVED_CACHE.get('inventory_snapshot_stats')
        if cached is not None:
            return cached  # type: ignore[return-value]
        # date -> {"total": float, "zero": int, "products": set, "warehouses": set}
        agg: dict[str, dict] = {}
        with _DERIVED_LOCK:
            cached = _DERIVED_CACHE.get('inventory_snapshot_stats')
            if cached is not None:
                return cached  # type: ignore[return-value]
            try:
                for chunk in pd.read_csv(
                    path,
                    usecols=['snapshot_date', 'warehouse_id', 'product_id', 'on_hand'],
                    chunksize=_INVENTORY_CHUNKS,
                ):
                    if chunk.empty:
                        del chunk
                        continue
                    for date, group in chunk.groupby('snapshot_date', sort=False):
                        state = agg.get(date)
                        if state is None:
                            state = agg[date] = {"total": 0.0, "zero": 0, "products": set(), "warehouses": set()}
                        state["total"] += float(group['on_hand'].sum())
                        state["zero"] += int(group['on_hand'].eq(0).sum())
                        state["products"].update(group['product_id'].astype(str).unique().tolist())
                        state["warehouses"].update(group['warehouse_id'].astype(str).unique().tolist())
                    del chunk
                gc.collect()
            except Exception:
                return {}
            if not agg:
                return {}
            latest = max(agg)
            state = agg[latest]
            result = {
                "latest_snapshot_date": latest,
                "total_on_hand": state["total"],
                "zero_stock_skus": state["zero"],
                "unique_products": len(state["products"]),
                "unique_warehouses": len(state["warehouses"]),
            }
            _DERIVED_CACHE['inventory_snapshot_stats'] = result
            return result
    def stockout_page(self, limit: int, offset: int, risk_level: str | None = None):
        path = self.root / 'stockout_predictions.csv'
        if not path.exists():
            return {'items': [], 'total': 0, 'limit': limit, 'offset': offset}
        items = []
        total = 0
        try:
            chunks = pd.read_csv(path, dtype=_STOCKOUT_DTYPES, chunksize=_STOCKOUT_CHUNKSIZE)
            for chunk in chunks:
                if risk_level and 'risk_level' in chunk.columns:
                    chunk = chunk[chunk['risk_level'].eq(risk_level)]
                chunk_len = len(chunk)
                if total + chunk_len > offset:
                    start = max(0, offset - total)
                    end = min(chunk_len, start + limit - len(items))
                    if end > start:
                        part = chunk.iloc[start:end]
                        items.extend(part.where(part.notna(), None).to_dict('records'))
                total += chunk_len
                del chunk
                if len(items) >= limit and total >= offset + limit:
                    break
            gc.collect()
        except Exception:
            return {'items': [], 'total': 0, 'limit': limit, 'offset': offset}
        return {'items': items, 'total': total, 'limit': limit, 'offset': offset}
    def stockout_risk_counts(self) -> dict:
        path = self.root / 'stockout_predictions.csv'
        if not path.exists():
            return {"count": 0, "high": 0, "critical": 0}
        high_pairs = set()
        critical_pairs = set()
        operational_pairs = set()
        levels: set[str] = set()
        try:
            chunks = pd.read_csv(path, usecols=['warehouse_id', 'product_id', 'risk_level'], dtype=_STOCKOUT_DTYPES, chunksize=_STOCKOUT_CHUNKSIZE)
            for chunk in chunks:
                if 'risk_level' not in chunk.columns:
                    del chunk
                    continue
                risk_col = chunk['risk_level']
                if hasattr(risk_col, 'cat'):
                    levels.update(str(v) for v in risk_col.cat.categories.tolist())
                else:
                    levels.update(str(v) for v in risk_col.dropna().unique().tolist())
                high = chunk['risk_level'].eq('High')
                critical = chunk['risk_level'].eq('Critical')
                if {'warehouse_id', 'product_id'}.issubset(chunk.columns):
                    high_df = chunk.loc[high, ['warehouse_id', 'product_id']].drop_duplicates()
                    pairs = set(zip(high_df['warehouse_id'].astype(str), high_df['product_id'].astype(str)))
                    high_pairs.update(pairs)
                    operational_pairs.update(pairs)
                    del high_df, pairs
                    critical_df = chunk.loc[critical, ['warehouse_id', 'product_id']].drop_duplicates()
                    pairs = set(zip(critical_df['warehouse_id'].astype(str), critical_df['product_id'].astype(str)))
                    critical_pairs.update(pairs)
                    operational_pairs.update(pairs)
                    del critical_df, pairs
                del chunk
            gc.collect()
            if levels:
                _DERIVED_CACHE['stockout_risk_levels'] = levels
        except Exception:
            return {"count": 0, "high": 0, "critical": 0}
        return {"count": len(operational_pairs), "high": len(high_pairs), "critical": len(critical_pairs)}
    def suppliers(self):
        return self._cached_small(('suppliers', self.root.resolve()), 'supplier_intelligence.csv')
    def warehouses(self):
        return self._cached_small(('warehouses', self.root.resolve()), 'warehouses.csv')
    def inventory(self): return self._read('inventory_snapshots.csv',dtype=_INVENTORY_DTYPES)
    def delivery(self):
        return self._cached_small(('delivery', self.root.resolve()), 'delivery_risk_predictions.csv')
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
    def _product_search_domain(self) -> list[str] | None:
        """Lower-cased product ids taken from recommended_inventory_by_warehouse
        (24 MB, covers all 32 951 catalogued products - verified).  Used to skip
        the 293 MB stockout scan when no known product can match the query.
        Returns None when the domain is unavailable or looks partial."""
        cached = _DERIVED_CACHE.get('product_search_domain')
        if cached is not None:
            return cached  # type: ignore[return-value]
        path = self.root / 'recommended_inventory_by_warehouse.csv'
        if not path.exists():
            return None
        try:
            frame = pd.read_csv(path, usecols=['product_id'])
        except Exception:
            return None
        if frame.empty or 'product_id' not in frame.columns:
            return None
        domain = sorted({str(v).lower() for v in frame['product_id'].dropna().unique().tolist()})
        if len(domain) < _PRODUCT_DOMAIN_MIN_PRODUCTS:
            return None
        _DERIVED_CACHE['product_search_domain'] = domain
        return domain

    def _warehouse_search_domain(self) -> list[str] | None:
        """Lower-cased warehouse ids from warehouses.csv (12 rows, cached).
        Returns None when the domain is unknown so callers never prune."""
        cached = _DERIVED_CACHE.get('warehouse_search_domain')
        if cached is not None:
            return cached  # type: ignore[return-value]
        try:
            frame = self.warehouses()
        except Exception:
            return None
        if frame is None or frame.empty or 'warehouse_id' not in frame.columns:
            return None
        domain = sorted({str(v).lower() for v in frame['warehouse_id'].dropna().unique().tolist()})
        if not domain:
            return None
        _DERIVED_CACHE['warehouse_search_domain'] = domain
        return domain

    def search(self, q: str):
        key = q.lower().strip()
        with _SEARCH_CACHE_LOCK:
            cached = _SEARCH_CACHE.get(key)
            if cached is not None:
                _SEARCH_CACHE.move_to_end(key)
                return [dict(item) for item in cached]
        out = self._compute_search(key)
        with _SEARCH_CACHE_LOCK:
            _SEARCH_CACHE[key] = [dict(item) for item in out]
            _SEARCH_CACHE.move_to_end(key)
            while len(_SEARCH_CACHE) > _SEARCH_CACHE_MAX:
                _SEARCH_CACHE.popitem(last=False)
        return out

    def _compute_search(self, q: str) -> list[dict]:
        out: list[dict] = []
        for name,kind,cols,usecols,dtypes in [('stockout_predictions.csv','SKU',['product_id','warehouse_id','risk_level'],['product_id','warehouse_id','risk_level'],_STOCKOUT_DTYPES),('supplier_intelligence.csv','Supplier',['supplier_id','supplier_name','risk_level'],['supplier_id','supplier_name','risk_level'],None),('warehouses.csv','Warehouse',['warehouse_id','city'],['warehouse_id','city'],None),('delivery_risk_predictions.csv','Shipment',['order_id','risk_level'],['order_id','risk_level'],None)]:
            dtype={k:v for k,v in dtypes.items() if k in usecols} if dtypes else None
            if name == 'stockout_predictions.csv':
                path = self.root / name
                if not path.exists():
                    continue
                read_cols = list(usecols)
                match_cols = list(cols)
                # product_id: every id in the file is a 32-char lowercase hex
                # string (verified over all 3.16 M rows) and the whole catalog is
                # known from recommended_inventory_by_warehouse.csv, so a query
                # that matches neither can never match a stockout row.
                if 'product_id' in match_cols:
                    if any(ch not in '0123456789abcdef' for ch in q):
                        match_cols.remove('product_id')
                    else:
                        product_domain = self._product_search_domain()
                        if product_domain is not None and not any(q in pid for pid in product_domain):
                            match_cols.remove('product_id')
                # warehouse_id domain comes from warehouses.csv (12 ids).  It is
                # also safe to drop the column from the read: warehouse_id is
                # never echoed back in the payload (only product_id/risk_level).
                wh_domain = self._warehouse_search_domain()
                if wh_domain is not None and 'warehouse_id' in match_cols:
                    if not any(q in w for w in wh_domain):
                        match_cols.remove('warehouse_id')
                        if 'warehouse_id' in read_cols:
                            read_cols.remove('warehouse_id')
                # risk_level domain = the code-defined label set (superset) plus
                # anything already observed while streaming the file.  A superset
                # can never cause a wrong skip.  The column stays in the read
                # (SKU rows echo risk_level back) - it is only un-matched.
                risk_domain = {str(level).lower() for level in _STOCKOUT_RISK_DOMAIN}
                observed_levels = _DERIVED_CACHE.get('stockout_risk_levels')
                if observed_levels:
                    risk_domain |= {str(level).lower() for level in observed_levels}
                if 'risk_level' in match_cols and not any(q in level for level in risk_domain):
                    match_cols.remove('risk_level')
                if not match_cols:
                    # Nothing in this file can match the query -> skip the scan.
                    continue
                dtype = {k: v for k, v in dtypes.items() if k in read_cols}
                found = 0
                seen = 0
                try:
                    # Bounded scan: chunks sized so no single allocation is
                    # large, a periodic gc.collect() so chunk frames return to
                    # the OS instead of growing RSS to ~330 MB, and an early
                    # exit once the 20 requested rows are collected.
                    for chunk in pd.read_csv(path, usecols=read_cols, dtype=dtype, chunksize=_SEARCH_CHUNKSIZE):
                        mask = None
                        for c in match_cols:
                            if c in chunk:
                                matched = _match_mask(chunk[c], q)
                                mask = matched if mask is None else (mask | matched)
                        if mask is not None and bool(mask.any()):
                            take = _SEARCH_MAX_RESULTS - found
                            if take > 0:
                                for r in chunk.loc[mask].head(take).to_dict('records'):
                                    rid = str(r.get(cols[0], ''))
                                    out.append({'type': kind, 'id': rid, 'label': rid, 'status': r.get('status'), 'risk_level': r.get('risk_level')})
                                    found += 1
                        seen += 1
                        del chunk, mask
                        if found >= _SEARCH_MAX_RESULTS:
                            break
                        if seen % _SEARCH_GC_EVERY == 0:
                            gc.collect()
                    gc.collect()
                except Exception:
                    pass
                continue
            df=self._read(name,usecols=usecols,dtype=dtype)
            if df.empty: continue
            mask=pd.Series(False,index=df.index)
            for c in cols:
                if c in df: mask |= _match_mask(df[c],q)
            for r in df[mask].head(_SEARCH_MAX_RESULTS).to_dict('records'):
                rid=str(r.get(cols[0],'')); out.append({'type':kind,'id':rid,'label':rid,'status':r.get('status'),'risk_level':r.get('risk_level')})
        return out
