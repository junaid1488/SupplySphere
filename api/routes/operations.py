from fastapi import APIRouter, HTTPException, Query
import gc
import pandas as pd
from api.services.data import DataRepository
from api.schemas.common import OptimizationRequest
router=APIRouter(prefix='/api',tags=['operations']); repo=DataRepository()

_forecast_cache = None

def page(df,limit,offset):
    part=df.iloc[offset:offset+limit]; return {'items':part.where(part.notna(),None).to_dict('records'),'total':len(df),'limit':limit,'offset':offset}

@router.get('/inventory')
def inventory(limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),risk_level:str|None=None):
    return repo.stockout_page(limit, offset, risk_level)
@router.get('/inventory/stockout-risk')
def stockout_risk(limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)): return repo.stockout_page(limit, offset)
@router.get('/suppliers')
def suppliers(limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)): return page(repo.suppliers(),limit,offset)
@router.get('/warehouses')
def warehouses(limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)): return page(repo.warehouses(),limit,offset)
@router.get('/logistics/delivery-risk')
def delivery(limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)): return page(repo.delivery(),limit,offset)
@router.get('/search')
def search(q:str=Query(min_length=1,max_length=100)): return {'items':repo.search(q)}
@router.get('/events')
def events(limit:int=100): return page(repo._read('shipment_events.csv'),limit,0)
@router.post('/optimization/run')
def optimization(req:OptimizationRequest):
    from ml.optimization.model import SupplyOptimizer
    suppliers=repo.suppliers(); warehouses=repo.warehouses(); demand=repo.demand()
    # Drop the 2.77 M historical inventory rows before anything else allocates:
    # solve() only reads the newest snapshot, and keeping the full frame alive
    # for the whole OR-Tools run is ~104 MB over the Render Free 512 MiB limit.
    inventory=SupplyOptimizer.latest_snapshot(repo.inventory())
    if req.product_id and not demand.empty: demand=demand[demand.product_id.astype(str)==req.product_id]
    if demand.empty: raise HTTPException(404,'Demand data unavailable for optimization')
    # Reuse existing optimizer contract; forecast_7d can be derived from recent demand.
    col='demand_units' if 'demand_units' in demand.columns else 'demand'
    demand=demand.assign(forecast_7d=demand.groupby('product_id')[col].transform(lambda s:s.tail(req.horizon_days).mean()*req.horizon_days))
    result=SupplyOptimizer().solve(suppliers,warehouses,demand,inventory)
    return {'solver':result.solver,'current_cost':result.current_cost,'optimized_cost':result.optimized_cost,'estimated_savings':result.current_cost-result.optimized_cost,'service_level':result.service_level,'stockout_risk':result.stockout_risk,'supplier_quantities':result.supplier_quantities.to_dict('records'),'warehouse_quantities':result.warehouse_quantities.to_dict('records'),'transfers':result.transfers.to_dict('records')}
@router.get('/optimization/results')
def optimization_results(): return repo.optimization()
@router.get('/demand/forecast')
def demand_forecast(limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)):
    global _forecast_cache
    if _forecast_cache is not None:
        return page(_forecast_cache, limit, offset)
    d=repo.forecast()
    if d.empty:
        dem=repo.demand()
        if dem.empty: return page(d,limit,offset)
        col='demand_units' if 'demand_units' in dem.columns else 'demand'
        d=dem.groupby('product_id',as_index=False).agg(demand_7d=(col,lambda s: float(s.tail(7).sum())),demand_30d=(col,lambda s: float(s.tail(30).sum())))
        del dem
        gc.collect()
    _forecast_cache = d
    return page(d,limit,offset)
@router.get('/inventory/{sku_id}')
def inventory_sku(sku_id:str):
    items = []
    offset = 0
    batch_size = 500
    while True:
        batch = repo.stockout_page(batch_size, offset)
        items.extend([r for r in batch['items'] if str(r.get('product_id','')) == sku_id])
        offset += batch_size
        if items or offset >= batch['total']:
            break
    if not items: raise HTTPException(404,'SKU not found')
    return {'items':items}
@router.get('/suppliers/{supplier_id}')
def supplier_detail(supplier_id:str):
    d=repo.suppliers(); x=d[d.supplier_id.astype(str)==supplier_id] if not d.empty else d
    if x.empty: raise HTTPException(404,'Supplier not found')
    return x.iloc[0].where(pd.notna(x.iloc[0]),None).to_dict()
@router.get('/warehouses/{warehouse_id}')
def warehouse_detail(warehouse_id:str):
    d=repo.warehouses(); x=d[d.warehouse_id.astype(str)==warehouse_id] if not d.empty else d
    if x.empty: raise HTTPException(404,'Warehouse not found')
    return x.iloc[0].where(pd.notna(x.iloc[0]),None).to_dict()
