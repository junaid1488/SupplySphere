"""STEP 19: API integration verification via TestClient (no live server needed)."""
from __future__ import annotations
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_health_phases(self):
        r = client.get("/api/health")
        assert r.json()["phases"] == "0-17"

    def test_health_components(self):
        r = client.get("/api/health")
        assert "dataset_analyzer" in r.json()["components"]


class TestDatasetAnalyzerAPIRoutes:
    def test_list_sessions(self):
        r = client.get("/api/dataset-analyzer/sessions")
        assert r.status_code == 200
        assert "sessions" in r.json()

    def test_get_nonexistent_returns_404(self):
        r = client.get("/api/dataset-analyzer/nonexistent/profile")
        assert r.status_code == 404

    def test_schema_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/schema")
        assert r.status_code == 404

    def test_capabilities_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/capabilities")
        assert r.status_code == 404

    def test_kpis_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/kpis")
        assert r.status_code == 404

    def test_analytics_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/analytics")
        assert r.status_code == 404

    def test_trends_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/trends")
        assert r.status_code == 404

    def test_domain_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/domain")
        assert r.status_code == 404

    def test_geospatial_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/geospatial")
        assert r.status_code == 404

    def test_routes_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/routes")
        assert r.status_code == 404

    def test_anomalies_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/anomalies")
        assert r.status_code == 404

    def test_insights_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/insights")
        assert r.status_code == 404

    def test_report_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/report")
        assert r.status_code == 404

    def test_queries_nonexistent(self):
        r = client.get("/api/dataset-analyzer/nonexistent/queries")
        assert r.status_code == 404

    def test_ask_nonexistent(self):
        r = client.post("/api/dataset-analyzer/nonexistent/ask", json={"question": "test"})
        assert r.status_code == 404


class TestRealtimeAPI:
    def test_start(self):
        r = client.post("/api/realtime/start")
        assert r.status_code == 200

    def test_tick(self):
        r = client.post("/api/realtime/tick")
        assert r.status_code == 200

    def test_status(self):
        r = client.get("/api/realtime/status")
        assert r.status_code == 200


class TestMLOpsAPI:
    def test_health(self):
        r = client.get("/api/mlops/health")
        assert r.status_code == 200
        assert r.json()["registry"] == "ok"


class TestRouterCompleteness:
    def test_all_expected_endpoints_exist(self):
        from dataset_analyzer.router import router
        routes = [route.path for route in router.routes]
        expected = [
            "/domain", "/geospatial", "/routes", "/anomalies",
            "/report", "/kpis", "/analytics", "/trends",
            "/queries", "/insights", "/ask",
        ]
        for ep in expected:
            assert any(ep in r for r in routes), f"Missing endpoint: {ep}"

    def test_session_manager_methods(self):
        from dataset_analyzer.session import SessionManager
        methods = [
            "compute_domain", "compute_geospatial", "compute_routes",
            "compute_anomalies", "answer_question", "compute_report",
            "compute_kpis", "compute_analytics", "compute_trends",
            "compute_insights", "compute_queries",
        ]
        for m in methods:
            assert hasattr(SessionManager, m), f"Missing method: {m}"
