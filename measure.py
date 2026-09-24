import requests
import time

base_url = 'http://127.0.0.1:8000'
endpoints = [
    ('Demand', '/api/geospatial/demand?limit=100'),
    ('Demand', '/api/geospatial/demand?limit=5000'),
    ('Inventory', '/api/geospatial/inventory?limit=100'),
    ('Inventory', '/api/geospatial/inventory?limit=5000'),
    ('Delivery', '/api/geospatial/delivery?limit=100'),
    ('Delivery', '/api/geospatial/delivery?limit=10000'),
]

for name, ep in endpoints:
    url = base_url + ep
    requests.get(url, timeout=30)
    times = []
    for i in range(3):
        start = time.time()
        r = requests.get(url, timeout=30)
        t = time.time() - start
        times.append(t)
    avg = sum(times) / len(times)
    data = r.json()
    items = len(data.get('items', []))
    total = data.get('total', 0)
    print(f'{name} {ep}: {avg:.3f}s (items: {items}, total: {total})')