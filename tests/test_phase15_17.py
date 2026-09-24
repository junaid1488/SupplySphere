from pathlib import Path
import pandas as pd
from fastapi.testclient import TestClient
from api.main import app
from realtime.events import SupplyEvent
from realtime.broker import InMemoryStream
from realtime.simulator import SupplyChainSimulator
from realtime.processor import EventProcessor
from mlops.monitoring import feature_drift, prediction_drift
from mlops.registry import ModelRegistry

client=TestClient(app)

def test_health_phase_17():
    r=client.get('/api/health'); assert r.status_code==200; assert r.json()['phases']=='0-17'

def test_event_validation_and_serialization():
    e=SupplyEvent.create('new_order','O-1',{'units':2}); d=e.to_dict(); assert d['event_type']=='new_order'; assert d['entity_id']=='O-1'
    try: SupplyEvent.create('bad','x',{})
    except ValueError: pass
    else: assert False

def test_inmemory_stream_and_processor():
    b=InMemoryStream(); b.publish({'event_type':'inventory_update'}); b.publish({'event_type':'shipment_delay'}); r=EventProcessor(b).process(); assert r.processed==2 and r.alerts==1

def test_simulator_controls_and_events():
    s=SupplyChainSimulator('data/processed',seed=42); assert s.tick_once() is None; s.start(); e=s.tick_once(); assert e and s.status()['processed']==1; s.pause(); assert s.tick_once() is None; s.stop()

def test_realtime_api():
    assert client.post('/api/realtime/start').status_code==200
    assert client.post('/api/realtime/tick').status_code==200
    assert client.get('/api/realtime/status').json()['running'] is True
    assert client.post('/api/realtime/pause').status_code==200

def test_monitoring_drift():
    a=pd.DataFrame({'x':[1,2,3,4],'y':[10,10,10,10]}); b=pd.DataFrame({'x':[3,4,5,6],'y':[10,10,10,10]}); m=feature_drift(a,b); assert any(x.feature=='x' and x.drift for x in m); assert prediction_drift(pd.Series([0.1,0.2]),pd.Series([0.8,0.9]))['drift']

def test_registry_lifecycle(tmp_path):
    r=ModelRegistry(tmp_path); rec=r.register('demo','1.0.0','ml/models/demo.joblib','dataset',['x'],{'a':1},{'f1':.8}); assert rec.stage=='candidate'; assert r.promote('demo','1.0.0')['stage']=='production'

def test_mlops_health():
    r=client.get('/api/mlops/health'); assert r.status_code==200; assert r.json()['registry']=='ok'

def test_required_phase_15_17_files():
    for f in ['realtime/events.py','realtime/broker.py','realtime/simulator.py','realtime/processor.py','mlops/registry.py','mlops/monitoring.py','mlops/integration.py','mlops/hardening/audit.py']:
        assert Path(f).exists()
