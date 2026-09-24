from fastapi.testclient import TestClient
from api.main import app
from geospatial.service import haversine_km, warehouse_features, route_table, transfer_points, INDIA_NETWORK, BRAZIL_NETWORK
from configs.settings import settings

client=TestClient(app)

INDIA_IDS=[f"WH-{i:03d}" for i in range(1,13)]
BRAZIL_IDS=[f"WH-{i:03d}" for i in range(1,16)]
INDIA_CITIES=["Delhi","Mumbai","Bengaluru","Hyderabad","Chennai","Kolkata","Lucknow","Jaipur","Pune","Ahmedabad","Patna","Guwahati"]

def test_health_phase_14():
    r=client.get('/api/health'); assert r.status_code==200; assert r.json()['phases']=='0-17'

def test_geospatial_warehouses_brazil_default():
    r=client.get('/api/geospatial/warehouses'); assert r.status_code==200; assert r.json()['total']==15
    items=r.json()['items']; assert [x['warehouse_id'] for x in items]==BRAZIL_IDS
    assert items[0]['city']=='São Paulo' and items[0]['warehouse_name']=='São Paulo Hub'

def test_geospatial_warehouses_india():
    r=client.get('/api/geospatial/warehouses?network=india'); assert r.status_code==200; assert r.json()['total']==12
    items=r.json()['items']; assert [x['warehouse_id'] for x in items]==INDIA_IDS
    assert [x['city'] for x in items]==INDIA_CITIES
    assert items[0]['latitude']==28.6139 and items[0]['longitude']==77.209
    assert items[11]['city']=='Guwahati' and items[11]['latitude']==26.1445 and items[11]['longitude']==91.7362

def test_networks_coexist_in_service():
    assert len(INDIA_NETWORK)==12 and len(BRAZIL_NETWORK)==15
    assert [n['warehouse_id'] for n in INDIA_NETWORK]==INDIA_IDS
    assert [n['warehouse_id'] for n in BRAZIL_NETWORK]==BRAZIL_IDS

def test_geospatial_routes():
    r=client.get('/api/geospatial/routes'); assert r.status_code==200; assert r.json()['items']
    assert len(r.json()['items'])==210
    r_i=client.get('/api/geospatial/routes?network=india'); assert r_i.status_code==200
    assert len(r_i.json()['items'])==132
    for item in r_i.json()['items']:
        assert item['origin_warehouse_id']!=item['destination_warehouse_id']
        assert item['origin_warehouse_id'] in INDIA_IDS and item['destination_warehouse_id'] in INDIA_IDS

def test_geospatial_transfers_both_networks():
    r_b=client.get('/api/geospatial/transfers?limit=5000'); assert r_b.status_code==200
    assert r_b.json()['total']==445
    r_i=client.get('/api/geospatial/transfers?network=india&limit=5000'); assert r_i.status_code==200
    assert r_i.json()['total']==445

def test_shipping_lanes_total():
    r=client.get('/api/geospatial/shipping-lanes?limit=1'); assert r.status_code==200
    assert r.json()['total']==112096

def test_haversine_zero(): assert haversine_km(0,0,0,0)==0

def test_dashboard_contract():
    r=client.get('/api/dashboard/summary'); assert r.status_code==200; assert 'stockout_risks' in r.json()

def test_inventory_pagination():
    r=client.get('/api/inventory?limit=5&offset=0'); assert r.status_code==200; assert len(r.json()['items'])<=5

def test_supplier_endpoint():
    r=client.get('/api/suppliers?limit=2'); assert r.status_code==200
    if r.json()['items']:
        sid=r.json()['items'][0]['supplier_id']; assert client.get(f'/api/suppliers/{sid}').status_code==200

def test_warehouse_endpoint():
    r=client.get('/api/warehouses?limit=2'); assert r.status_code==200
    if r.json()['items']:
        wid=r.json()['items'][0]['warehouse_id']; assert client.get(f'/api/warehouses/{wid}').status_code==200

def test_search_contract(): assert client.get('/api/search?q=WH-001').status_code==200

def test_demand_forecast_contract(): assert client.get('/api/demand/forecast?limit=3').status_code==200

def test_delivery_risk_contract(): assert client.get('/api/logistics/delivery-risk?limit=3').status_code==200

def test_shipment_not_found_is_404(): assert client.get('/api/shipments/not-a-real-shipment').status_code==404

def test_optimization_contract():
    r=client.post('/api/optimization/run',json={}); assert r.status_code in (200,404)

def test_frontend_leaflet_source():
    text=open('frontend/src/OlistControlTower.tsx',encoding='utf-8').read(); assert "from 'leaflet'" in text and 'openstreetmap.org' in text

def test_phase14_tracking_timeline_source():
    text=open('api/routes/tracking.py',encoding='utf-8').read(); assert 'timeline' in text and '/shipments/' in text
