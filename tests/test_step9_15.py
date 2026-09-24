from __future__ import annotations
import io
import tempfile
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

from dataset_analyzer.models import (
    DatasetProfile,
    ColumnProfile,
    InferredType,
    SemanticRole,
    SchemaIntelligence,
    SemanticRoleDetection,
    CapabilityDetection,
    Capability,
    CapabilityStatus,
)
from dataset_analyzer.storage import DatasetStorage
from dataset_analyzer.session import SessionManager
from dataset_analyzer.reader import create_reader
from dataset_analyzer.profiler import create_profiler
from dataset_analyzer.schema_intelligence import create_schema_intelligence_analyzer
from dataset_analyzer.capability_detection import create_capability_detector
from dataset_analyzer.domain_engine import create_domain_engine
from dataset_analyzer.geospatial_engine import create_geospatial_engine
from dataset_analyzer.route_engine import create_route_engine
from dataset_analyzer.anomaly_engine import create_anomaly_engine
from dataset_analyzer.query_engine import create_query_engine
from dataset_analyzer.insights_engine import create_insights_engine
from dataset_analyzer.report_engine import create_report_engine


def _create_synthetic_csv() -> bytes:
    np.random.seed(42)
    n = 50
    products = np.random.choice(["Widget A", "Widget B", "Gadget X", "Gadget Y", "Tool Z"], n)
    sales = np.random.uniform(10, 1000, n).round(2)
    quantity = np.random.randint(1, 100, n)
    stock = np.random.randint(0, 500, n)
    stock[5] = 0
    stock[10] = 0
    stock[15] = 0

    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    expiry_dates = []
    for i in range(n):
        if i < 10:
            expiry_dates.append((pd.Timestamp("2025-06-01") + pd.Timedelta(days=i)).strftime("%Y-%m-%d"))
        elif i < 20:
            expiry_dates.append((pd.Timestamp("2025-09-15") + pd.Timedelta(days=i)).strftime("%Y-%m-%d"))
        else:
            expiry_dates.append((pd.Timestamp("2026-03-01") + pd.Timedelta(days=i)).strftime("%Y-%m-%d"))

    suppliers = np.random.choice(["Supplier Alpha", "Supplier Beta", "Supplier Gamma"], n)
    loss = np.zeros(n)
    loss[3] = 50.0
    loss[7] = 120.0
    loss[25] = 300.0

    lats = np.random.uniform(-90, 90, n).round(6)
    lons = np.random.uniform(-180, 180, n).round(6)
    lats[0] = 999.0
    lons[1] = -999.0
    lats[2] = None
    lons[2] = None

    origins = np.random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"], n)
    destinations = np.random.choice(["London", "Paris", "Tokyo", "Berlin", "Sydney"], n)

    employee = [f"Emp_{i:03d}" for i in range(n)]
    departments = np.random.choice(["Sales", "Logistics", "Warehouse", "Admin"], n)
    salary = np.random.uniform(30000, 120000, n).round(2)
    salary[40] = 500000.0
    salary[41] = 500000.0

    categories = np.random.choice(["Electronics", "Furniture", "Clothing", "Food"], n)

    df = pd.DataFrame({
        "product": products,
        "sales": sales,
        "quantity": quantity,
        "date": dates.strftime("%Y-%m-%d"),
        "stock": stock,
        "expiry_date": expiry_dates,
        "supplier": suppliers,
        "loss": loss,
        "latitude": lats,
        "longitude": lons,
        "origin": origins,
        "destination": destinations,
        "employee": employee,
        "department": departments,
        "salary": salary,
        "category": categories,
    })

    duplicate_row = df.iloc[0:1].copy()
    df = pd.concat([df, duplicate_row], ignore_index=True)

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


@pytest.fixture
def synthetic_session():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "test_storage"
        storage = DatasetStorage(base_path=base, ttl_seconds=3600)
        manager = SessionManager(storage=storage)

        content = _create_synthetic_csv()
        file_obj = io.BytesIO(content)
        session = manager.create_session("synthetic_test.csv", file_obj, len(content))
        yield manager, session


class TestStep9DomainEngine:
    def test_domain_computation(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_domain(session.dataset_id)
        assert result is not None
        assert result.dataset_id == session.dataset_id
        assert len(result.results) > 0
        domains_found = [r.domain for r in result.results]
        assert "product_sales" in domains_found or "inventory" in domains_found
        for r in result.results:
            assert r.available is True
            assert len(r.source_columns) > 0
            assert len(r.calculation_basis) > 0

    def test_domain_product_sales(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_domain(session.dataset_id)
        product_results = [r for r in result.results if r.domain == "product_sales"]
        if product_results:
            pr = product_results[0]
            assert "product" in pr.source_columns or any("product" in c for c in pr.source_columns)
            assert pr.available is True

    def test_domain_inventory(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_domain(session.dataset_id)
        inv_results = [r for r in result.results if r.domain == "inventory"]
        if inv_results:
            ir = inv_results[0]
            assert ir.available is True
            assert any("stock" in c for c in ir.source_columns)

    def test_domain_expiry(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_domain(session.dataset_id)
        expiry_results = [r for r in result.results if r.domain == "expiry"]
        assert len(expiry_results) > 0
        er = expiry_results[0]
        assert er.available is True
        assert any("expiry" in c for c in er.source_columns)

    def test_domain_supplier(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_domain(session.dataset_id)
        supplier_results = [r for r in result.results if r.domain == "supplier"]
        assert len(supplier_results) > 0
        sr = supplier_results[0]
        assert sr.available is True
        assert any("supplier" in c for c in sr.source_columns)

    def test_domain_loss_damage(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_domain(session.dataset_id)
        loss_results = [r for r in result.results if r.domain == "loss_damage"]
        assert len(loss_results) > 0
        lr = loss_results[0]
        assert lr.available is True
        assert any("loss" in c for c in lr.source_columns)

    def test_domain_serialization(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_domain(session.dataset_id)
        d = result.to_dict()
        assert "dataset_id" in d
        assert "results" in d
        assert "computed_at" in d
        assert isinstance(d["results"], list)


class TestStep10GeospatialEngine:
    def test_geospatial_computation(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_geospatial(session.dataset_id)
        assert result is not None
        assert result.dataset_id == session.dataset_id
        geo = result.geospatial
        assert geo.total_records > 0
        assert geo.valid_coordinate_count + geo.invalid_coordinate_count == geo.total_records

    def test_geospatial_valid_invalid(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_geospatial(session.dataset_id)
        geo = result.geospatial
        assert geo.valid_coordinate_count > 0
        assert geo.invalid_coordinate_count > 0
        assert geo.valid_percentage > 0
        assert geo.valid_percentage < 100

    def test_geospatial_bounding_box(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_geospatial(session.dataset_id)
        geo = result.geospatial
        bb = geo.bounding_box
        assert bb["min_lat"] is not None
        assert bb["max_lat"] is not None
        assert bb["min_lon"] is not None
        assert bb["max_lon"] is not None
        assert bb["min_lat"] <= bb["max_lat"]
        assert bb["min_lon"] <= bb["max_lon"]
        assert -90 <= bb["min_lat"] <= 90
        assert -90 <= bb["max_lat"] <= 90
        assert -180 <= bb["min_lon"] <= 180
        assert -180 <= bb["max_lon"] <= 180

    def test_geospatial_source_columns(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_geospatial(session.dataset_id)
        geo = result.geospatial
        assert "latitude" in geo.source_columns
        assert "longitude" in geo.source_columns

    def test_geospatial_distribution(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_geospatial(session.dataset_id)
        geo = result.geospatial
        assert isinstance(geo.coordinate_distribution, dict)

    def test_geospatial_serialization(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_geospatial(session.dataset_id)
        d = result.to_dict()
        assert "geospatial" in d
        assert "dataset_id" in d


class TestStep11RouteEngine:
    def test_route_computation(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_routes(session.dataset_id)
        assert result is not None
        assert result.dataset_id == session.dataset_id

    def test_route_origins_destinations(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_routes(session.dataset_id)
        routes = result.routes
        assert routes.unique_origins > 0
        assert routes.unique_destinations > 0
        assert routes.unique_routes > 0

    def test_route_top_routes(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_routes(session.dataset_id)
        routes = result.routes
        assert len(routes.top_routes) > 0
        for tr in routes.top_routes:
            assert "route" in tr
            assert "frequency" in tr
            assert tr["frequency"] > 0

    def test_route_frequency(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_routes(session.dataset_id)
        routes = result.routes
        assert len(routes.route_frequency) > 0
        for route, count in routes.route_frequency.items():
            assert count > 0

    def test_route_volume(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_routes(session.dataset_id)
        routes = result.routes
        assert routes.route_volume is not None
        assert routes.route_volume > 0

    def test_route_source_columns(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_routes(session.dataset_id)
        routes = result.routes
        assert "origin" in routes.source_columns
        assert "destination" in routes.source_columns

    def test_route_serialization(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_routes(session.dataset_id)
        d = result.to_dict()
        assert "routes" in d
        assert "dataset_id" in d


class TestStep12AnomalyEngine:
    def test_anomaly_computation(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_anomalies(session.dataset_id)
        assert result is not None
        assert result.dataset_id == session.dataset_id

    def test_anomaly_detection(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_anomalies(session.dataset_id)
        assert len(result.anomalies) > 0

    def test_anomaly_method(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_anomalies(session.dataset_id)
        for anomaly in result.anomalies:
            assert anomaly.method in ("IQR", "robust_zscore", "standard_zscore")

    def test_anomaly_source_columns(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_anomalies(session.dataset_id)
        valid_numeric_cols = {"salary", "sales", "loss", "stock", "quantity", "latitude", "longitude"}
        for anomaly in result.anomalies:
            assert len(anomaly.source_columns) > 0
            assert anomaly.source_columns[0] in valid_numeric_cols

    def test_anomaly_affected_rows(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_anomalies(session.dataset_id)
        for anomaly in result.anomalies:
            assert anomaly.affected_rows > 0
            assert anomaly.total_rows > 0
            assert anomaly.affected_rows <= anomaly.total_rows

    def test_anomaly_outlier_detection(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_anomalies(session.dataset_id)
        salary_anomalies = [a for a in result.anomalies if "salary" in a.source_columns]
        if salary_anomalies:
            assert salary_anomalies[0].affected_rows >= 2

    def test_anomaly_serialization(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_anomalies(session.dataset_id)
        d = result.to_dict()
        assert "anomalies" in d
        assert "dataset_id" in d


class TestStep13QueryEngine:
    def test_query_engine_column_coverage(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_queries(session.dataset_id)
        assert result is not None
        assert result.total_searchable > 0
        assert result.column_coverage > 0

    def test_query_how_many_rows(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "How many rows are in the dataset?")
        assert result.supported is True
        assert result.answer == 51

    def test_query_how_many_columns(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "How many columns are there?")
        assert result.supported is True
        assert result.answer == 16

    def test_query_average_sales(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "What is the average sales?")
        assert result.supported is True
        assert result.answer is not None
        assert result.result_type == "average"
        assert "sales" in result.source_columns

    def test_query_total_sales(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "What is the total sales?")
        assert result.supported is True
        assert result.answer is not None
        assert result.result_type == "total"

    def test_query_highest_sales(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "What is the highest sales?")
        assert result.supported is True
        assert result.result_type == "maximum"

    def test_query_lowest_stock(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "What is the lowest stock?")
        assert result.supported is True
        assert result.result_type == "minimum"

    def test_query_count_suppliers(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "How many suppliers are there?")
        assert result.supported is True
        assert result.result_type == "distinct_count"
        assert result.answer == 3

    def test_query_count_products(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "How many products are there?")
        assert result.supported is True
        assert result.result_type == "distinct_count"

    def test_query_unsupported(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "What is the meaning of life?")
        assert result.supported is False
        assert result.reason is not None

    def test_query_column_info(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "What is sales?")
        assert result.supported is True
        assert result.result_type == "column_info"
        assert result.answer["column"] == "sales"

    def test_query_trend(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "Show sales trend over time")
        assert result.supported is True
        assert result.result_type == "trend_reference"

    def test_query_trend_simple(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "sales trend over time")
        assert result.supported is True
        assert result.result_type == "trend_reference"

    def test_query_category_highest(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "Which category has the highest sales?")
        assert result.supported is True
        assert result.result_type == "top_category"

    def test_query_serialization(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.answer_question(session.dataset_id, "How many rows?")
        d = result.to_dict()
        assert "question" in d
        assert "answer" in d
        assert "supported" in d


class TestStep14InsightsEngine:
    def test_insights_computation(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_insights(session.dataset_id)
        assert result is not None
        assert result.dataset_id == session.dataset_id
        assert len(result.insights) > 0

    def test_insight_stockout_risk(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_insights(session.dataset_id)
        stockout = [i for i in result.insights if i.name == "stockout_risk"]
        assert len(stockout) > 0
        so = stockout[0]
        assert so.value in ("low", "medium", "high")
        assert "stock" in so.source_columns[0]
        assert len(so.calculation_basis) > 0

    def test_insight_supplier_diversity(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_insights(session.dataset_id)
        supplier = [i for i in result.insights if i.name == "supplier_diversity"]
        assert len(supplier) > 0
        sp = supplier[0]
        assert sp.value == 3
        assert "supplier" in sp.source_columns[0]

    def test_insight_data_quality(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_insights(session.dataset_id)
        dup = [i for i in result.insights if i.name == "data_quality_duplicate_rate"]
        assert len(dup) > 0
        assert dup[0].value >= 0

    def test_insight_missingness(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_insights(session.dataset_id)
        miss = [i for i in result.insights if i.name == "data_missingness"]
        assert len(miss) > 0
        assert miss[0].value >= 0

    def test_insight_no_causal_claims(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_insights(session.dataset_id)
        for insight in result.insights:
            basis_lower = insight.calculation_basis.lower()
            assert "caused" not in basis_lower
            assert "resulted in" not in basis_lower
            assert "led to" not in basis_lower

    def test_insight_serialization(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_insights(session.dataset_id)
        d = result.to_dict()
        assert "insights" in d
        assert "dataset_id" in d


class TestStep15ReportEngine:
    def test_report_computation(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_report(session.dataset_id)
        assert result is not None
        assert result.dataset_id == session.dataset_id

    def test_report_has_all_sections(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_report(session.dataset_id)
        assert result.kpis is not None
        assert result.analytics is not None
        assert result.trends is not None
        assert result.domain is not None
        assert result.geospatial is not None
        assert result.routes is not None
        assert result.anomalies is not None
        assert result.queries is not None
        assert result.insights is not None

    def test_report_dataset_summary(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_report(session.dataset_id)
        summary = result.dataset_summary
        assert summary["row_count"] == 51
        assert summary["column_count"] == 16
        assert len(summary["column_names"]) == 16
        assert summary["missing_value_rate_pct"] >= 0

    def test_report_unavailable_section(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_report(session.dataset_id)
        assert isinstance(result.unavailable, dict)

    def test_report_source_columns_preserved(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_report(session.dataset_id)
        d = result.to_dict()
        assert "dataset_summary" in d
        assert "kpis" in d
        assert "analytics" in d
        assert "domain" in d
        assert "geospatial" in d
        assert "routes" in d
        assert "anomalies" in d
        assert "insights" in d

    def test_report_serialization(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_report(session.dataset_id)
        d = result.to_dict()
        assert "dataset_id" in d
        assert "computed_at" in d
        assert "unavailable" in d


class TestAPIIntegration:
    def test_api_imports(self):
        from dataset_analyzer.router import router
        assert router is not None
        assert router.prefix == "/api/dataset-analyzer"

    def test_api_session_manager_has_new_methods(self):
        manager = SessionManager.__new__(SessionManager)
        assert hasattr(SessionManager, "compute_domain")
        assert hasattr(SessionManager, "compute_geospatial")
        assert hasattr(SessionManager, "compute_routes")
        assert hasattr(SessionManager, "compute_anomalies")
        assert hasattr(SessionManager, "answer_question")
        assert hasattr(SessionManager, "compute_report")

    def test_api_all_endpoints_exist(self):
        from dataset_analyzer.router import router
        routes = [route.path for route in router.routes]
        assert any("/domain" in r for r in routes)
        assert any("/geospatial" in r for r in routes)
        assert any("/routes" in r for r in routes)
        assert any("/anomalies" in r for r in routes)
        assert any("/report" in r for r in routes)
        assert any("/kpis" in r for r in routes)
        assert any("/analytics" in r for r in routes)
        assert any("/trends" in r for r in routes)
        assert any("/queries" in r for r in routes)
        assert any("/insights" in r for r in routes)
        assert any("/ask" in r for r in routes)


class TestNoFakeDataVerification:
    def test_no_fake_geography(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_geospatial(session.dataset_id)
        geo = result.geospatial
        assert "cities" not in str(geo.to_dict())
        assert "states" not in str(geo.to_dict())
        assert "countries" not in str(geo.to_dict())
        assert "addresses" not in str(geo.to_dict())

    def test_no_fake_supplier_metrics(self, synthetic_session):
        manager, session = synthetic_session
        domain_result = manager.compute_domain(session.dataset_id)
        for r in domain_result.results:
            if r.domain == "supplier":
                for key, val in r.metrics.items():
                    if "row_count" in key.lower():
                        assert False, f"Supplier metric uses row count: {key}"

    def test_expiry_only_when_detected(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_domain(session.dataset_id)
        expiry_results = [r for r in result.results if r.domain == "expiry"]
        assert len(expiry_results) > 0
        er = expiry_results[0]
        assert "expiry_date" in er.source_columns

    def test_route_distances_called_correctly(self, synthetic_session):
        manager, session = synthetic_session
        result = manager.compute_routes(session.dataset_id)
        d = result.to_dict()
        route_str = str(d)
        assert "road distance" not in route_str.lower()
        assert "travel distance" not in route_str.lower()
        assert "eta" not in route_str.lower()
        assert "network distance" not in route_str.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
