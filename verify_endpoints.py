import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

endpoints = [
    "/api/health",
    "/api/dashboard/summary",
    "/api/inventory?limit=12",
    "/api/inventory/stockout-risk?limit=12",
    "/api/suppliers?limit=12",
    "/api/warehouses?limit=12",
    "/api/logistics/delivery-risk?limit=12",
    "/api/demand/forecast?limit=12",
    "/api/search?q=WH-001",
    "/api/events?limit=10",
    "/api/optimization/results",
    "/api/geospatial/warehouses",
    "/api/geospatial/customers?limit=10000",
    "/api/geospatial/sellers?limit=5000",
    "/api/geospatial/orders?limit=5000",
    "/api/geospatial/demand?limit=5000",
    "/api/geospatial/inventory?limit=5000",
    "/api/geospatial/delivery?limit=5000",
    "/api/geospatial/transfers?limit=5000",
    "/api/geospatial/routes",
    # Frontend contract limit tests
    "/api/geospatial/customers?limit=10000",
    "/api/geospatial/orders?limit=10000",
    "/api/geospatial/delivery?limit=10000",
]

def verify_endpoint(url):
    full_url = BASE_URL + url
    try:
        req = urllib.request.Request(full_url)
        with urllib.request.urlopen(req, timeout=30) as response:
            status = response.status
            data = response.read()
            payload = json.loads(data)
            
            print(f"\n=== {url} ===")
            print(f"Status: {status}")
            print(f"JSON Parse: OK")
            
            if isinstance(payload, dict) and "items" in payload:
                items = payload["items"]
                print(f"Type: dict with items")
                print(f"Item count: {len(items)}")
                print(f"Total: {payload.get('total', 'N/A')}")
                print(f"Limit: {payload.get('limit', 'N/A')}")
                print(f"Offset: {payload.get('offset', 'N/A')}")
                if items:
                    print(f"First record keys: {list(items[0].keys())}")
            elif isinstance(payload, list):
                print(f"Type: list")
                print(f"Item count: {len(payload)}")
                if payload:
                    print(f"First record keys: {list(payload[0].keys())}")
            else:
                print(f"Type: dict")
                print(f"Keys: {list(payload.keys())}")
            
            return True, status, payload
    except urllib.error.HTTPError as e:
        print(f"\n=== {url} ===")
        print(f"Status: {e.code}")
        print(f"Error: HTTP {e.code}")
        try:
            error_body = e.read()
            print(f"Error body: {error_body.decode()}")
        except:
            pass
        return False, e.code, None
    except urllib.error.URLError as e:
        print(f"\n=== {url} ===")
        print(f"Error: URL Error - {e.reason}")
        return False, 0, None
    except json.JSONDecodeError as e:
        print(f"\n=== {url} ===")
        print(f"Error: JSON Decode Error - {e}")
        return False, 0, None
    except Exception as e:
        print(f"\n=== {url} ===")
        print(f"Error: {type(e).__name__} - {e}")
        return False, 0, None

if __name__ == "__main__":
    print("Starting endpoint verification...")
    print(f"Base URL: {BASE_URL}")
    
    results = []
    for endpoint in endpoints:
        success, status, payload = verify_endpoint(endpoint)
        results.append((endpoint, success, status))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for endpoint, success, status in results:
        status_str = "PASS" if success else "FAIL"
        print(f"{status_str:4} | {status:3} | {endpoint}")