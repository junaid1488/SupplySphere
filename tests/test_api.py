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


def _stub_warm_steps(monkeypatch, calls):
    import api.main as main
    monkeypatch.setattr(main.dashboard, "_warm_caches", lambda: calls.append("dashboard"))
    monkeypatch.setattr(main, "_warm_geospatial", lambda deadline: calls.append("geospatial"))
    monkeypatch.setattr(main.insights, "insights", lambda: calls.append("insights"))
    monkeypatch.setattr(main.reports, "reports", lambda: calls.append("reports"))
    monkeypatch.setitem(main._WARM_STATE, "done", False)
    return main


def test_warmup_runs_every_step_within_budget(monkeypatch):
    calls = []
    main = _stub_warm_steps(monkeypatch, calls)
    monkeypatch.setattr(main, "_WARM_BUDGET_SECONDS", 60.0)
    main._warm_expensive_routes()
    assert calls == ["dashboard", "geospatial", "insights", "reports"]
    assert main._WARM_STATE["done"] is True


def test_warmup_stops_when_budget_is_spent(monkeypatch):
    calls = []
    main = _stub_warm_steps(monkeypatch, calls)
    monkeypatch.setattr(main, "_WARM_BUDGET_SECONDS", -1.0)
    main._warm_expensive_routes()
    assert calls == []
    assert main._WARM_STATE["done"] is True


def test_warmup_reports_warm_even_when_a_step_fails(monkeypatch):
    calls = []
    main = _stub_warm_steps(monkeypatch, calls)
    monkeypatch.setattr(main, "_WARM_BUDGET_SECONDS", 60.0)

    def boom():
        raise RuntimeError("warm step exploded")

    monkeypatch.setattr(main.dashboard, "_warm_caches", boom)
    main._warm_expensive_routes()
    assert calls == ["geospatial", "insights", "reports"]
    assert main._WARM_STATE["done"] is True


def test_geospatial_payload_cache_is_bounded():
    import pandas as pd
    from api.routes import geospatial as geo

    geo._PAYLOAD_CACHE.clear()
    try:
        for i in range(geo._CACHE_LIMIT + 5):
            geo._cached_records(f"bounded-{i}", lambda: pd.DataFrame({"a": [1, 2]}), 2, 0)
        assert len(geo._PAYLOAD_CACHE) <= geo._CACHE_LIMIT
    finally:
        geo._PAYLOAD_CACHE.clear()
