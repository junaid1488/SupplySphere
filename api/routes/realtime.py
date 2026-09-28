from fastapi import APIRouter, Query
from realtime.simulator import SupplyChainSimulator

router=APIRouter(prefix='/api/realtime',tags=['realtime'])
_simulator: SupplyChainSimulator | None = None

def _get_simulator() -> SupplyChainSimulator:
    global _simulator
    if _simulator is None:
        _simulator = SupplyChainSimulator()
    return _simulator

@router.post('/start')
def start(): return _get_simulator().start()
@router.post('/pause')
def pause(): return _get_simulator().pause()
@router.post('/stop')
def stop(): return _get_simulator().stop()
@router.post('/tick')
def tick():
    sim=_get_simulator()
    event=sim.tick_once()
    return {'running':sim.state.running,'event':event,'status':sim.status()}
@router.get('/status')
def status(): return _get_simulator().status()
@router.get('/stream')
def stream(limit:int=Query(100,ge=1,le=1000)):
    sim=_get_simulator()
    return {'items':sim.broker.consume(limit),'total':sim.broker.size() if hasattr(sim.broker,'size') else None}
