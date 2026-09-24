from fastapi import APIRouter, Query
from realtime.simulator import SupplyChainSimulator

router=APIRouter(prefix='/api/realtime',tags=['realtime'])
simulator=SupplyChainSimulator()

@router.post('/start')
def start(): return simulator.start()
@router.post('/pause')
def pause(): return simulator.pause()
@router.post('/stop')
def stop(): return simulator.stop()
@router.post('/tick')
def tick():
    event=simulator.tick_once()
    return {'running':simulator.state.running,'event':event,'status':simulator.status()}
@router.get('/status')
def status(): return simulator.status()
@router.get('/stream')
def stream(limit:int=Query(100,ge=1,le=1000)): return {'items':simulator.broker.consume(limit),'total':simulator.broker.size() if hasattr(simulator.broker,'size') else None}
