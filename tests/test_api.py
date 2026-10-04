from fastapi.testclient import TestClient
from api.main import app

def test_health():
    c=TestClient(app)
    r=c.get("/api/health")
    assert r.status_code==200
    assert r.json()["status"]=="ok"

def test_health_head():
    c=TestClient(app)
    r=c.head("/api/health")
    assert r.status_code==200
    assert r.content == b""
