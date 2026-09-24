import requests
base_url = 'http://127.0.0.1:8000'
eps = ['/api/geospatial/customers?limit=100', '/api/geospatial/sellers?limit=100', '/api/geospatial/orders?limit=100', '/api/geospatial/transfers?limit=100']
for ep in eps:
    r = requests.get(base_url + ep, timeout=30)
    d = r.json()
    print(f'{ep}: items={len(d["items"])}, total={d["total"]}')