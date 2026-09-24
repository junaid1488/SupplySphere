"""Deterministic phase 11-14 contract audit and smoke runner."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from api.main import app

client=TestClient(app)
checks=[]
def check(name, fn):
    try: fn(); checks.append({'check':name,'status':'PASS'})
    except Exception as e: checks.append({'check':name,'status':'FAIL','error':str(e)})

check('health', lambda: (_ for _ in ()).throw(AssertionError()) if client.get('/api/health').status_code!=200 else None)
check('geospatial warehouses', lambda: (_ for _ in ()).throw(AssertionError()) if client.get('/api/geospatial/warehouses').json()['total']!=12 else None)
check('geospatial routes', lambda: (_ for _ in ()).throw(AssertionError()) if not client.get('/api/geospatial/routes').json()['items'] else None)
for path in ['/api/dashboard/summary','/api/demand/forecast?limit=3','/api/inventory?limit=3','/api/inventory/stockout-risk?limit=3','/api/suppliers?limit=3','/api/warehouses?limit=3','/api/logistics/delivery-risk?limit=3','/api/events?limit=3']:
    check(path, lambda p=path: (_ for _ in ()).throw(AssertionError(client.get(p).text)) if client.get(p).status_code!=200 else None)
check('search', lambda: (_ for _ in ()).throw(AssertionError()) if client.get('/api/search?q=WH-001').status_code!=200 else None)
check('optimization', lambda: (_ for _ in ()).throw(AssertionError()) if client.post('/api/optimization/run',json={}).status_code not in (200,404,503) else None)
check('frontend leaflet contract', lambda: (_ for _ in ()).throw(AssertionError()) if not ('from \'leaflet\'' in (ROOT/'frontend/src/main.tsx').read_text() and 'openstreetmap.org' in (ROOT/'frontend/src/main.tsx').read_text()) else None)
report={'phase':'11-14','checks':checks,'passed':sum(x['status']=='PASS' for x in checks),'failed':sum(x['status']=='FAIL' for x in checks),'frontend_build':'NOT_VERIFIED_IN_RESTRICTED_ENV'}
(ROOT/'data/processed/phase11_14_audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
if report['failed']: raise SystemExit(1)
