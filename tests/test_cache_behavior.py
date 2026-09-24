"""Verify computation cache eliminates repeated profiling across compute endpoints."""
from __future__ import annotations
import io
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from dataset_analyzer.models import DatasetProfile
from dataset_analyzer.storage import DatasetStorage
from dataset_analyzer.session import SessionManager


def _make_csv_bytes(n_rows: int = 50) -> bytes:
    np.random.seed(42)
    df = pd.DataFrame({
        "product": np.random.choice(["A", "B", "C"], n_rows),
        "sales": np.random.uniform(10, 1000, n_rows).round(2),
        "quantity": np.random.randint(1, 100, n_rows),
    })
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


class TestComputationCache:
    def test_profile_cached_across_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = DatasetStorage(base_path=Path(tmp) / "storage")
            manager = SessionManager(storage=storage)
            content = _make_csv_bytes()
            session = manager.create_session("test.csv", io.BytesIO(content), len(content))
            ds = session.dataset_id

            with patch(
                "dataset_analyzer.session.create_profiler",
                wraps=__import__("dataset_analyzer.session", fromlist=["create_profiler"]).create_profiler,
            ) as mock_create:
                p1 = manager.profile_dataset(ds)
                p2 = manager.profile_dataset(ds)
                p3 = manager.profile_dataset(ds)

                assert p1.row_count == p2.row_count == p3.row_count
                assert mock_create.call_count == 1, (
                    f"create_profiler called {mock_create.call_count} times; expected 1"
                )

    def test_analyze_schema_reuses_cached_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = DatasetStorage(base_path=Path(tmp) / "storage")
            manager = SessionManager(storage=storage)
            content = _make_csv_bytes()
            session = manager.create_session("test.csv", io.BytesIO(content), len(content))
            ds = session.dataset_id

            with patch(
                "dataset_analyzer.session.create_profiler",
                wraps=__import__("dataset_analyzer.session", fromlist=["create_profiler"]).create_profiler,
            ) as mock_create:
                manager.profile_dataset(ds)
                manager.analyze_schema(ds)
                assert mock_create.call_count == 1, (
                    f"analyze_schema triggered extra profiling: {mock_create.call_count} calls"
                )

    def test_detect_capabilities_reuses_cached_profile_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = DatasetStorage(base_path=Path(tmp) / "storage")
            manager = SessionManager(storage=storage)
            content = _make_csv_bytes()
            session = manager.create_session("test.csv", io.BytesIO(content), len(content))
            ds = session.dataset_id

            with patch(
                "dataset_analyzer.session.create_profiler",
                wraps=__import__("dataset_analyzer.session", fromlist=["create_profiler"]).create_profiler,
            ) as mock_create:
                manager.detect_capabilities(ds)
                assert mock_create.call_count == 1, (
                    f"detect_capabilities triggered extra profiling: {mock_create.call_count} calls"
                )

    def test_multiple_compute_endpoints_share_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = DatasetStorage(base_path=Path(tmp) / "storage")
            manager = SessionManager(storage=storage)
            content = _make_csv_bytes()
            session = manager.create_session("test.csv", io.BytesIO(content), len(content))
            ds = session.dataset_id

            with patch(
                "dataset_analyzer.session.create_profiler",
                wraps=__import__("dataset_analyzer.session", fromlist=["create_profiler"]).create_profiler,
            ) as mock_create:
                manager.compute_kpis(ds)
                manager.compute_analytics(ds)
                manager.compute_trends(ds)
                manager.compute_domain(ds)
                manager.compute_geospatial(ds)
                manager.compute_routes(ds)
                manager.compute_anomalies(ds)
                manager.compute_insights(ds)
                manager.compute_report(ds)

                assert mock_create.call_count == 1, (
                    f"9 compute endpoints caused {mock_create.call_count} profiling calls; expected 1"
                )

    def test_delete_clears_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = DatasetStorage(base_path=Path(tmp) / "storage")
            manager = SessionManager(storage=storage)
            content = _make_csv_bytes()
            session = manager.create_session("test.csv", io.BytesIO(content), len(content))
            ds = session.dataset_id

            manager.profile_dataset(ds)
            assert ds in manager._computation_cache
            assert "profile" in manager._computation_cache[ds]

            manager.delete_session(ds)
            assert ds not in manager._computation_cache

    def test_results_identical_with_and_without_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = DatasetStorage(base_path=Path(tmp) / "storage")
            manager = SessionManager(storage=storage)
            content = _make_csv_bytes()
            session = manager.create_session("test.csv", io.BytesIO(content), len(content))
            ds = session.dataset_id

            r1 = manager.compute_kpis(ds)
            r2 = manager.compute_report(ds)
            assert r1 is not None
            assert r2 is not None

            manager._computation_cache.clear()
            r3 = manager.compute_kpis(ds)
            d1 = r1.to_dict()
            d3 = r3.to_dict()
            assert d1["kpis"] == d3["kpis"], "KPI values differ after cache clear and recompute"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
