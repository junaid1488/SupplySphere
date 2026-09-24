from __future__ import annotations
import io
import tempfile
from pathlib import Path

import pytest
import pandas as pd

from dataset_analyzer.storage import DatasetStorage
from dataset_analyzer.session import SessionManager
from dataset_analyzer.profiler import create_profiler
from dataset_analyzer.schema_intelligence import create_schema_intelligence_analyzer
from dataset_analyzer.capability_detection import create_capability_detector
from dataset_analyzer.kpi_engine import create_kpi_engine
from dataset_analyzer.analytics_engine import create_analytics_engine
from dataset_analyzer.trend_engine import create_trend_engine
from dataset_analyzer.models import FileFormat, SemanticRole


class TestContext:
    def __init__(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name) / "test_storage"
        self.storage = DatasetStorage(base_path=self.base, ttl_seconds=3600)
        self.manager = SessionManager(storage=self.storage)

    def create_session(self, content: bytes, filename: str = "test.csv"):
        file_obj = io.BytesIO(content)
        return self.manager.create_session(filename, file_obj, len(content))

    def get_full_pipeline(self, session):
        profile = self.manager.profile_dataset(session.metadata.dataset_id)
        schema = self.manager.analyze_schema(session.metadata.dataset_id)
        capabilities = self.manager.detect_capabilities(session.metadata.dataset_id)
        return profile, schema, capabilities

    def cleanup(self):
        self.tmpdir.cleanup()


@pytest.fixture
def test_context():
    ctx = TestContext()
    yield ctx
    ctx.cleanup()


class TestKPIEngine:
    def test_dataset_overview_kpis(self, test_context):
        content = b"col1,col2,col3\n1,2,3\n4,5,6\n7,8,9\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_kpi_engine(profile, schema, capabilities)
        report = engine.compute_all()

        kpi_names = [k.name for k in report.kpis]
        assert "row_count" in kpi_names
        assert "column_count" in kpi_names
        assert "missing_value_rate" in kpi_names
        assert "duplicate_row_count" in kpi_names
        assert "duplicate_row_rate" in kpi_names

        row_count_kpi = next(k for k in report.kpis if k.name == "row_count")
        assert row_count_kpi.value == 3
        assert row_count_kpi.available is True
        assert row_count_kpi.source_columns == ["col1", "col2", "col3"]

    def test_numeric_kpis(self, test_context):
        content = b"value,amount\n10,100\n20,200\n30,300\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_kpi_engine(profile, schema, capabilities)
        report = engine.compute_all()

        kpi_names = [k.name for k in report.kpis]
        assert "value_sum" in kpi_names
        assert "value_mean" in kpi_names
        assert "value_median" in kpi_names
        assert "value_min" in kpi_names
        assert "value_max" in kpi_names
        assert "amount_sum" in kpi_names

        value_sum = next(k for k in report.kpis if k.name == "value_sum")
        assert value_sum.value == 60
        assert value_sum.source_columns == ["value"]
        assert "Sum of non-null values in value" in value_sum.calculation_basis

    def test_schema_aware_kpis_sales(self, test_context):
        content = b"price,revenue\n100,1000\n200,2000\n300,3000\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_kpi_engine(profile, schema, capabilities)
        report = engine.compute_all()

        kpi_names = [k.name for k in report.kpis]
        sales_kpis = [k for k in report.kpis if k.name.startswith("sales_")]
        assert len(sales_kpis) > 0

        for kpi in sales_kpis:
            assert kpi.available is True
            assert len(kpi.source_columns) > 0

    def test_schema_aware_kpis_inventory(self, test_context):
        content = b"stock_level,quantity\n10,5\n0,3\n20,7\n0,2\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_kpi_engine(profile, schema, capabilities)
        report = engine.compute_all()

        kpi_names = [k.name for k in report.kpis]
        inventory_kpis = [k for k in report.kpis if "inventory" in k.name or "zero_stock" in k.name]
        assert len(inventory_kpis) > 0

    def test_missing_fields_handled(self, test_context):
        content = b"name,category\nA,X\nB,Y\nC,Z\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_kpi_engine(profile, schema, capabilities)
        report = engine.compute_all()

        numeric_kpis = [k for k in report.kpis if k.name.endswith("_sum") or k.name.endswith("_mean")]
        for kpi in numeric_kpis:
            assert kpi.available is False
            assert kpi.reason is not None


class TestAnalyticsEngine:
    def test_numeric_aggregations(self, test_context):
        content = b"value,amount\n10,100\n20,200\n30,300\n40,400\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_analytics_engine(profile, schema)
        report = engine.compute_all()

        agg_results = [r for r in report.results if r.result_type == "numeric_aggregations"]
        assert len(agg_results) == 2

        for result in agg_results:
            assert result.available is True
            assert "count" in result.data
            assert "mean" in result.data
            assert "std" in result.data

    def test_category_frequency(self, test_context):
        content = b"category,value\nA,10\nA,20\nB,30\nC,40\nC,50\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_analytics_engine(profile, schema)
        report = engine.compute_all()

        freq_results = [r for r in report.results if r.result_type == "category_frequency"]
        assert len(freq_results) == 1

        result = freq_results[0]
        assert result.available is True
        assert "categories" in result.data
        assert result.data["unique_categories"] == 3

    def test_groupby_analysis(self, test_context):
        content = b"category,value\nA,10\nA,20\nB,30\nB,40\nC,50\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_analytics_engine(
            profile, schema,
            reader_provider=lambda: test_context.manager.get_reader(session.metadata.dataset_id)
        )
        report = engine.compute_all()

        groupby_results = [r for r in report.results if r.result_type == "groupby_analysis"]
        assert len(groupby_results) > 0

        for result in groupby_results:
            assert result.available is True
            assert isinstance(result.data, list)
            if result.data:
                assert "count" in result.data[0]
                assert "mean" in result.data[0]

    def test_correlation_analysis(self, test_context):
        content = b"x,y,z\n" + b"\n".join(f"{i},{i*2},{i*3}".encode() for i in range(20))
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_analytics_engine(
            profile, schema,
            reader_provider=lambda: test_context.manager.get_reader(session.metadata.dataset_id)
        )
        report = engine.compute_all()

        corr_results = [r for r in report.results if r.result_type == "correlation"]
        assert len(corr_results) == 1

        result = corr_results[0]
        assert result.available is True
        assert "pairs" in result.data
        assert len(result.data["pairs"]) == 3

        for pair in result.data["pairs"]:
            assert abs(pair["correlation"] - 1.0) < 0.001

    def test_top_bottom_categories(self, test_context):
        content = b"category,value\nA,10\nA,20\nB,100\nB,200\nC,5\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_analytics_engine(
            profile, schema,
            reader_provider=lambda: test_context.manager.get_reader(session.metadata.dataset_id)
        )
        report = engine.compute_all()

        tb_results = [r for r in report.results if r.result_type == "top_bottom_categories"]
        assert len(tb_results) > 0

        for result in tb_results:
            assert result.available is True
            assert "top" in result.data
            assert "bottom" in result.data


class TestTrendEngine:
    def test_valid_date_numeric_produces_trend(self, test_context):
        content = b"date,value\n2024-01-01,10\n2024-01-02,20\n2024-01-03,30\n2024-01-04,40\n2024-01-05,50\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_trend_engine(
            profile, schema,
            reader_provider=lambda: test_context.manager.get_reader(session.metadata.dataset_id)
        )
        report = engine.compute_all()

        assert len(report.trends) == 1
        trend = report.trends[0]
        assert trend.available is True
        assert trend.date_column == "date"
        assert trend.measure_column == "value"
        assert trend.aggregation_period in ("D", "W", None)
        assert len(trend.data) >= 3
        assert trend.trend_direction in ("increasing", "decreasing", "stable")
        assert trend.trend_summary is not None
        assert "slope" in trend.trend_summary
        assert "r_squared" in trend.trend_summary

    def test_missing_date_returns_unavailable(self, test_context):
        content = b"category,value\nA,10\nB,20\nC,30\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_trend_engine(
            profile, schema,
            reader_provider=lambda: test_context.manager.get_reader(session.metadata.dataset_id)
        )
        report = engine.compute_all()

        assert len(report.trends) == 1
        trend = report.trends[0]
        assert trend.available is False
        assert trend.name == "no_valid_trends"
        assert "date/time column" in trend.reason.lower()

    def test_missing_numeric_measure_returns_unavailable(self, test_context):
        content = b"date,category\n2024-01-01,A\n2024-01-02,B\n2024-01-03,C\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_trend_engine(
            profile, schema,
            reader_provider=lambda: test_context.manager.get_reader(session.metadata.dataset_id)
        )
        report = engine.compute_all()

        assert len(report.trends) == 1
        trend = report.trends[0]
        assert trend.available is False

    def test_insufficient_observations(self, test_context):
        content = b"date,value\n2024-01-01,10\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_trend_engine(
            profile, schema,
            reader_provider=lambda: test_context.manager.get_reader(session.metadata.dataset_id)
        )
        report = engine.compute_all()

        trend = report.trends[0]
        if trend.name != "no_valid_trends":
            assert trend.available is False
            assert "Insufficient" in trend.reason or "insufficient" in trend.reason.lower()

    def test_irregular_dates_handled(self, test_context):
        content = b"date,value\n2024-01-01,10\n2024-01-05,20\n2024-01-10,30\n2024-02-01,40\n2024-03-01,50\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_trend_engine(
            profile, schema,
            reader_provider=lambda: test_context.manager.get_reader(session.metadata.dataset_id)
        )
        report = engine.compute_all()

        trend = report.trends[0]
        assert trend.available is True
        assert len(trend.data) >= 3

    def test_deterministic_results(self, test_context):
        content = b"date,value\n2024-01-01,10\n2024-01-02,20\n2024-01-03,30\n2024-01-04,40\n2024-01-05,50\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        reader_provider = lambda: test_context.manager.get_reader(session.metadata.dataset_id)
        engine1 = create_trend_engine(profile, schema, reader_provider=reader_provider)
        report1 = engine1.compute_all()

        engine2 = create_trend_engine(profile, schema, reader_provider=reader_provider)
        report2 = engine2.compute_all()

        trend1 = report1.trends[0]
        trend2 = report2.trends[0]

        assert trend1.trend_direction == trend2.trend_direction
        assert trend1.trend_summary["slope"] == trend2.trend_summary["slope"]
        assert trend1.data == trend2.data


class TestDatasetIsolation:
    def test_separate_sessions_produce_separate_results(self, test_context):
        content1 = b"date,value\n2024-01-01,10\n2024-01-02,20\n"
        content2 = b"date,value\n2024-01-01,100\n2024-01-02,200\n"

        session1 = test_context.create_session(content1)
        session2 = test_context.create_session(content2)

        kpis1 = test_context.manager.compute_kpis(session1.metadata.dataset_id)
        kpis2 = test_context.manager.compute_kpis(session2.metadata.dataset_id)

        assert kpis1.dataset_id != kpis2.dataset_id

        sum1 = next(k for k in kpis1.kpis if k.name == "value_sum")
        sum2 = next(k for k in kpis2.kpis if k.name == "value_sum")

        assert sum1.value == 30
        assert sum2.value == 300


class TestAPIEndpoints:
    def test_kpi_endpoint_structure(self, test_context):
        content = b"date,value\n2024-01-01,10\n2024-01-02,20\n"
        session = test_context.create_session(content)

        kpis = test_context.manager.compute_kpis(session.metadata.dataset_id)
        data = kpis.to_dict()
        assert "dataset_id" in data
        assert "kpis" in data
        assert "computed_at" in data
        assert isinstance(data["kpis"], list)

    def test_analytics_endpoint_structure(self, test_context):
        content = b"category,value\nA,10\nB,20\n"
        session = test_context.create_session(content)

        analytics = test_context.manager.compute_analytics(session.metadata.dataset_id)
        data = analytics.to_dict()
        assert "dataset_id" in data
        assert "results" in data
        assert "computed_at" in data
        assert isinstance(data["results"], list)

    def test_trends_endpoint_structure(self, test_context):
        content = b"date,value\n2024-01-01,10\n2024-01-02,20\n"
        session = test_context.create_session(content)

        trends = test_context.manager.compute_trends(session.metadata.dataset_id)
        data = trends.to_dict()
        assert "dataset_id" in data
        assert "trends" in data
        assert "computed_at" in data
        assert isinstance(data["trends"], list)

    def test_invalid_dataset_id_returns_404(self, test_context):
        try:
            test_context.manager.compute_kpis("ds_invalid")
            assert False, "Should have raised SessionNotFoundError"
        except Exception as e:
            assert "not found" in str(e).lower() or "invalid" in str(e).lower()

        try:
            test_context.manager.compute_analytics("ds_invalid")
            assert False, "Should have raised SessionNotFoundError"
        except Exception as e:
            assert "not found" in str(e).lower() or "invalid" in str(e).lower()

        try:
            test_context.manager.compute_trends("ds_invalid")
            assert False, "Should have raised SessionNotFoundError"
        except Exception as e:
            assert "not found" in str(e).lower() or "invalid" in str(e).lower()


class TestKPISourceColumns:
    def test_kpi_source_columns_correct(self, test_context):
        content = b"price,quantity\n10,5\n20,3\n"
        session = test_context.create_session(content)
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_kpi_engine(profile, schema, capabilities)
        report = engine.compute_all()

        price_sum = next(k for k in report.kpis if k.name == "price_sum")
        assert price_sum.source_columns == ["price"]

        qty_sum = next(k for k in report.kpis if k.name == "quantity_sum")
        assert qty_sum.source_columns == ["quantity"]


class TestTrendAggregationPeriod:
    def test_daily_aggregation_for_dense_dates(self, test_context):
        dates = [f"2024-01-{i:02d}" for i in range(1, 31)]
        content = "date,value\n" + "\n".join(f"{d},{i*10}" for i, d in enumerate(dates, 1))
        session = test_context.create_session(content.encode())
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_trend_engine(
            profile, schema,
            reader_provider=lambda: test_context.manager.get_reader(session.metadata.dataset_id)
        )
        report = engine.compute_all()

        trend = report.trends[0]
        assert trend.available is True
        assert trend.aggregation_period in ("D", "W")

    def test_monthly_aggregation_for_sparse_dates(self, test_context):
        dates = ["2024-01-15", "2024-02-15", "2024-03-15", "2024-04-15", "2024-05-15"]
        content = "date,value\n" + "\n".join(f"{d},{i*100}" for i, d in enumerate(dates, 1))
        session = test_context.create_session(content.encode())
        profile, schema, capabilities = test_context.get_full_pipeline(session)

        engine = create_trend_engine(
            profile, schema,
            reader_provider=lambda: test_context.manager.get_reader(session.metadata.dataset_id)
        )
        report = engine.compute_all()

        trend = report.trends[0]
        assert trend.available is True
        assert trend.aggregation_period in ("M", "Q")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])