import requests
base_url = 'http://127.0.0.1:8000'

# Test demand with limit=100
r = requests.get(base_url + '/api/geospatial/demand?limit=100', timeout=30)
d = r.json()
print(f'demand limit=100: items={len(d["items"])}, total={d["total"]}')

# Test demand with limit=10000
r = requests.get(base_url + '/api/geospatial/demand?limit=10000', timeout=30)
d = r.json()
print(f'demand limit=10000: items={len(d["items"])}, total={d["total"]}')

# Test demand with limit=100 again
r = requests.get(base_url + '/api/geospatial/demand?limit=100', timeout=30)
d = r.json()
print(f'demand limit=100 (again): items={len(d["items"])}, total={d["total"]}')