from fastapi import APIRouter, HTTPException
from api.services.data import DataRepository
router=APIRouter(prefix='/api',tags=['tracking']); repo=DataRepository()
@router.get('/shipments/{shipment_id}')
def shipment(shipment_id:str):
    d=repo.delivery()
    if d.empty or 'order_id' not in d: raise HTTPException(404,'Shipment not found')
    x=d[d.order_id.astype(str)==shipment_id]
    if x.empty: raise HTTPException(404,'Shipment not found')
    r=x.iloc[0].to_dict(); events=repo._read('shipment_events.csv'); ev=events[events.order_id.astype(str)==shipment_id].to_dict('records') if not events.empty and 'order_id' in events else []
    return {'shipment':r,'timeline':ev}
