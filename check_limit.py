import requests
base_url = 'http://127.0.0.1:8000'
r = requests.get(base_url + '/api/geospatial/customers?limit=5', timeout=30)
d = r.json()
print(f'limit=5: items={len(d["items"])}, total={d["total"]}')
r = requests.get(base_url + '/api/geospatial/customers?limit=100', timeout=30)
d = r.json()
print(f'limit=100: items={len(d["items"])}, total={d["total"]}')