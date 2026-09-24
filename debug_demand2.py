import requests
base_url = 'http://127.0.0.1:8000'

# Test demand with limit=10000
r = requests.get(base_url + '/api/geospatial/demand?limit=10000', timeout=30)
print(f'Status: {r.status_code}')
print(f'Response: {r.text[:500]}')