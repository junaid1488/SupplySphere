from __future__ import annotations
import io
import json
import tempfile
from pathlib import Path

import pytest
import pandas as pd

from dataset_analyzer.models import (
    DatasetMetadata,
    DatasetSession,
    DatasetStatus,
    FileFormat,
    generate_dataset_id,
    InferredType,
    SemanticRole,
    CapabilityStatus,
    ColumnProfile,
    DatasetProfile,
    SemanticRoleDetection,
    SchemaIntelligence,
    Capability,
    CapabilityDetection,
)
from dataset_analyzer.session import (
    SessionManager,
    SessionError,
    SessionNotFoundError,
    SessionExpiredError,
    ReaderSessionError,
    ProfilingError,
)
from dataset_analyzer.storage import (
    DatasetStorage,
    PathSafetyError,
    StorageError,
    ContentValidationError,
    FileSizeLimitError,
    EmptyFileError,
)
from dataset_analyzer.reader import DatasetReader, ReaderError, create_reader
from dataset_analyzer.profiler import create_profiler, DatasetProfiler
from dataset_analyzer.schema_intelligence import create_schema_intelligence_analyzer, SchemaIntelligenceAnalyzer
from dataset_analyzer.capability_detection import create_capability_detector, CapabilityDetector


class TestDatasetModels:
    def test_generate_dataset_id(self):
        id1 = generate_dataset_id()
        id2 = generate_dataset_id()
        assert id1.startswith("ds_")
        assert len(id1) == 19
        assert id1 != id2

    def test_dataset_metadata_roundtrip(self):
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        expires = now + timedelta(hours=1)

        metadata = DatasetMetadata(
            dataset_id="ds_test123",
            original_filename="test.csv",
            file_format=FileFormat.CSV,
            file_size_bytes=1024,
            content_hash="abc123",
            created_at=now,
            expires_at=expires,
            status=DatasetStatus.READY,
            row_count=100,
            column_count=5,
            column_names=["a", "b", "c", "d", "e"],
            column_types={"a": "int", "b": "str"},
        )

        d = metadata.to_dict()
        restored = DatasetMetadata.from_dict(d)

        assert restored.dataset_id == metadata.dataset_id
        assert restored.original_filename == metadata.original_filename
        assert restored.file_format == metadata.file_format
        assert restored.file_size_bytes == metadata.file_size_bytes
        assert restored.content_hash == metadata.content_hash
        assert restored.created_at == metadata.created_at
        assert restored.expires_at == metadata.expires_at
        assert restored.status == metadata.status
        assert restored.row_count == metadata.row_count
        assert restored.column_count == metadata.column_count
        assert restored.column_names == metadata.column_names
        assert restored.column_types == metadata.column_types


class TestDatasetStorage:
    def test_storage_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            assert storage.base_path == base.resolve()
            assert storage.base_path.exists()

    def test_create_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n1,2\n3,4\n"
            file_obj = io.BytesIO(content)

            session = storage.create_session("test.csv", file_obj, len(content))

            assert session.metadata.dataset_id.startswith("ds_")
            assert session.metadata.original_filename == "test.csv"
            assert session.metadata.file_format == FileFormat.CSV
            assert session.metadata.file_size_bytes == len(content)
            assert session.metadata.content_hash is not None
            assert session.metadata.status == DatasetStatus.UPLOADING
            assert session.storage_path.exists()
            assert session.storage_path.read_bytes() == content

    def test_get_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            session = storage.create_session("test.csv", file_obj, len(content))
            dataset_id = session.metadata.dataset_id

            retrieved = storage.get_session(dataset_id)

            assert retrieved is not None
            assert retrieved.metadata.dataset_id == dataset_id
            assert retrieved.metadata.original_filename == "test.csv"
            assert retrieved.storage_path.read_bytes() == content

    def test_get_nonexistent_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            result = storage.get_session("ds_nonexistent")
            assert result is None

    def test_update_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            session = storage.create_session("test.csv", file_obj, len(content))
            dataset_id = session.metadata.dataset_id

            updated = storage.update_metadata(
                dataset_id,
                status=DatasetStatus.READY.value,
                row_count=10,
                column_count=2,
            )

            assert updated.status == DatasetStatus.READY
            assert updated.row_count == 10
            assert updated.column_count == 2

            retrieved = storage.get_session(dataset_id)
            assert retrieved.metadata.status == DatasetStatus.READY
            assert retrieved.metadata.row_count == 10

    def test_delete_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            session = storage.create_session("test.csv", file_obj, len(content))
            dataset_id = session.metadata.dataset_id

            deleted = storage.delete_session(dataset_id)
            assert deleted is True

            retrieved = storage.get_session(dataset_id)
            assert retrieved is None

    def test_delete_nonexistent_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            deleted = storage.delete_session("ds_nonexistent")
            assert deleted is False

    def test_list_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            for i in range(3):
                content = f"col1,col2\n{i},{i+1}\n".encode()
                file_obj = io.BytesIO(content)
                storage.create_session(f"test{i}.csv", file_obj, len(content))

            sessions = storage.list_sessions()
            assert len(sessions) == 3

    def test_path_safety_valid_dataset_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            session = storage.create_session("test.csv", file_obj, len(content))
            dataset_id = session.metadata.dataset_id

            retrieved = storage.get_session(dataset_id)
            assert retrieved is not None

    def test_path_safety_invalid_dataset_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            with pytest.raises(PathSafetyError):
                storage.get_session("../etc/passwd")

            with pytest.raises(PathSafetyError):
                storage.get_session("ds_../../../etc/passwd")

            with pytest.raises(PathSafetyError):
                storage.get_session("ds_test/../other")

    def test_path_safety_malformed_dataset_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            with pytest.raises(PathSafetyError):
                storage.get_session("invalid_id")

            with pytest.raises(PathSafetyError):
                storage.get_session("")

    def test_unsupported_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"data"
            file_obj = io.BytesIO(content)

            with pytest.raises(StorageError):
                storage.create_session("test.txt", file_obj, len(content))

    def test_cleanup_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=-1)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            storage.create_session("test.csv", file_obj, len(content))

            cleaned = storage.cleanup_expired()
            assert cleaned == 1

            sessions = storage.list_sessions()
            assert len(sessions) == 0


class TestSessionManager:
    def test_create_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n1,2\n3,4\n"
            file_obj = io.BytesIO(content)

            session = manager.create_session("test.csv", file_obj, len(content))

            assert session.metadata.dataset_id.startswith("ds_")
            assert session.metadata.original_filename == "test.csv"
            assert session.metadata.status == DatasetStatus.UPLOADING

    def test_create_session_file_too_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage, max_file_size=100)

            content = b"x" * 200
            file_obj = io.BytesIO(content)

            with pytest.raises(SessionError):
                manager.create_session("test.csv", file_obj, len(content))

    def test_get_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            session = manager.create_session("test.csv", file_obj, len(content))
            dataset_id = session.metadata.dataset_id

            retrieved = manager.get_session(dataset_id)
            assert retrieved.metadata.dataset_id == dataset_id

    def test_get_nonexistent_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            with pytest.raises(SessionNotFoundError):
                manager.get_session("ds_nonexistent")

    def test_get_expired_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=-1)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            session = manager.create_session("test.csv", file_obj, len(content))
            dataset_id = session.metadata.dataset_id

            with pytest.raises(SessionExpiredError):
                manager.get_session(dataset_id)

    def test_update_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            session = manager.create_session("test.csv", file_obj, len(content))
            dataset_id = session.metadata.dataset_id

            updated = manager.update_status(dataset_id, DatasetStatus.READY)
            assert updated.status == DatasetStatus.READY

            updated = manager.update_status(dataset_id, DatasetStatus.ERROR, "Test error")
            assert updated.status == DatasetStatus.ERROR
            assert updated.error_message == "Test error"

    def test_update_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            session = manager.create_session("test.csv", file_obj, len(content))
            dataset_id = session.metadata.dataset_id

            updated = manager.update_profile(
                dataset_id,
                row_count=100,
                column_count=5,
                column_names=["a", "b", "c", "d", "e"],
                column_types={"a": "int", "b": "str"},
            )

            assert updated.status == DatasetStatus.READY
            assert updated.row_count == 100
            assert updated.column_count == 5
            assert updated.column_names == ["a", "b", "c", "d", "e"]
            assert updated.column_types == {"a": "int", "b": "str"}

    def test_delete_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            session = manager.create_session("test.csv", file_obj, len(content))
            dataset_id = session.metadata.dataset_id

            deleted = manager.delete_session(dataset_id)
            assert deleted is True

            with pytest.raises(SessionNotFoundError):
                manager.get_session(dataset_id)

    def test_list_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            for i in range(3):
                content = f"col1,col2\n{i},{i+1}\n".encode()
                file_obj = io.BytesIO(content)
                manager.create_session(f"test{i}.csv", file_obj, len(content))

            sessions = manager.list_sessions()
            assert len(sessions) == 3

    def test_cleanup_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=-1)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            manager.create_session("test.csv", file_obj, len(content))

            cleaned = manager.cleanup_expired()
            assert cleaned == 1

            sessions = manager.list_sessions()
            assert len(sessions) == 0

    def test_get_storage_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            session = manager.create_session("test.csv", file_obj, len(content))
            dataset_id = session.metadata.dataset_id

            path = manager.get_storage_path(dataset_id)
            assert path.exists()
            assert path.read_bytes() == content


class TestDatasetIsolation:
    def test_storage_separate_from_olist_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "supplysphere_dataset_analyzer"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            olist_dirs = [
                Path("data/raw"),
                Path("data/staging"),
                Path("data/processed"),
                Path("ml/models"),
            ]

            for olist_dir in olist_dirs:
                assert not str(storage.base_path).startswith(str(olist_dir))
                assert not str(olist_dir).startswith(str(storage.base_path))

    def test_no_olist_data_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "supplysphere_dataset_analyzer"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)
            session = manager.create_session("user_data.csv", file_obj, len(content))

            assert "olist" not in session.metadata.original_filename.lower()
            assert session.metadata.dataset_id.startswith("ds_")
            assert session.storage_path.parent.name == session.metadata.dataset_id

    def test_multiple_sessions_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "supplysphere_dataset_analyzer"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content1 = b"a,b\n1,2\n"
            content2 = b"x,y\n3,4\n"
            session1 = manager.create_session("data1.csv", io.BytesIO(content1), len(content1))
            session2 = manager.create_session("data2.csv", io.BytesIO(content2), len(content2))

            assert session1.metadata.dataset_id != session2.metadata.dataset_id
            assert session1.storage_path != session2.storage_path
            assert session1.storage_path.parent != session2.storage_path.parent

            path1 = manager.get_storage_path(session1.metadata.dataset_id)
            path2 = manager.get_storage_path(session2.metadata.dataset_id)

            assert path1.read_bytes() == b"a,b\n1,2\n"
            assert path2.read_bytes() == b"x,y\n3,4\n"

    def test_path_traversal_prevention(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "supplysphere_dataset_analyzer"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            with pytest.raises((SessionError, PathSafetyError)):
                manager.get_session("ds_../../../etc/passwd")

            with pytest.raises((SessionError, PathSafetyError)):
                manager.get_storage_path("ds_../../../etc/passwd")


class TestAPIEndpoints:
    def test_router_import(self):
        from dataset_analyzer.router import router
        assert router is not None
        assert router.prefix == "/api/dataset-analyzer"

    def test_module_imports(self):
        from dataset_analyzer import (
            DatasetMetadata,
            DatasetSession,
            DatasetStatus,
            FileFormat,
            DatasetStorage,
            SessionManager,
            router,
        )
        assert DatasetMetadata is not None
        assert DatasetSession is not None
        assert DatasetStatus is not None
        assert FileFormat is not None
        assert DatasetStorage is not None
        assert SessionManager is not None
        assert router is not None


class TestSecureUpload:
    def test_valid_csv_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n1,2\n3,4\n"
            file_obj = io.BytesIO(content)
            session = storage.create_session("test.csv", file_obj, len(content))

            assert session.metadata.file_format == FileFormat.CSV
            assert session.metadata.file_size_bytes == len(content)

    def test_valid_xlsx_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            import pandas as pd
            df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
            xlsx_buffer = io.BytesIO()
            df.to_excel(xlsx_buffer, index=False)
            xlsx_content = xlsx_buffer.getvalue()

            file_obj = io.BytesIO(xlsx_content)
            session = storage.create_session("test.xlsx", file_obj, len(xlsx_content))

            assert session.metadata.file_format == FileFormat.XLSX
            assert session.metadata.file_size_bytes == len(xlsx_content)

    def test_valid_xls_upload(self):
        pytest.skip("XLS format not supported (xlwt deprecated), use XLSX")

    def test_empty_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b""
            file_obj = io.BytesIO(content)

            with pytest.raises(EmptyFileError):
                storage.create_session("test.csv", file_obj, len(content))

    def test_malformed_csv_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"\x00\x01\x02\x03"
            file_obj = io.BytesIO(content)

            with pytest.raises(ContentValidationError):
                storage.create_session("test.csv", file_obj, len(content))

    def test_malformed_xlsx_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"not a real xlsx file"
            file_obj = io.BytesIO(content)

            with pytest.raises(ContentValidationError):
                storage.create_session("test.xlsx", file_obj, len(content))

    def test_oversized_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600, max_file_size=100)

            content = b"x" * 200
            file_obj = io.BytesIO(content)

            with pytest.raises(FileSizeLimitError):
                storage.create_session("test.csv", file_obj, len(content))

    def test_declared_size_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)

            with pytest.raises(StorageError):
                storage.create_session("test.csv", file_obj, declared_size=999)

    def test_unsupported_extension_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"data"
            file_obj = io.BytesIO(content)

            with pytest.raises(StorageError):
                storage.create_session("test.txt", file_obj, len(content))

            with pytest.raises(StorageError):
                storage.create_session("test.pdf", file_obj, len(content))

    def test_traversal_filename_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)

            session = storage.create_session("../../../etc/passwd.csv", file_obj, len(content))

            assert session.metadata.original_filename == "../../../etc/passwd.csv"
            assert session.storage_path.name == "data.csv"
            assert ".." not in str(session.storage_path)

    def test_absolute_path_filename_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n1,2\n"
            file_obj = io.BytesIO(content)

            session = storage.create_session("/absolute/path/test.csv", file_obj, len(content))

            assert session.storage_path.name == "data.csv"

    def test_failed_upload_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"not a valid xlsx"
            file_obj = io.BytesIO(content)

            try:
                storage.create_session("test.xlsx", file_obj, len(content))
            except ContentValidationError:
                pass

            sessions = storage.list_sessions()
            assert len(sessions) == 0

    def test_streaming_upload_no_full_ram(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600, max_file_size=10_000)

            content = b"col1,col2\n" + b"x" * 5000 + b"\n"
            file_obj = io.BytesIO(content)

            session = storage.create_session("test.csv", file_obj, len(content))

            assert session.metadata.file_size_bytes == len(content)
            assert session.storage_path.read_bytes() == content


class TestDatasetReader:
    def _create_csv_session(self, storage, content: bytes):
        file_obj = io.BytesIO(content)
        return storage.create_session("test.csv", file_obj, len(content))

    def _create_xlsx_session(self, storage, df_dict: dict):
        import pandas as pd
        df = pd.DataFrame(df_dict)
        xlsx_buffer = io.BytesIO()
        df.to_excel(xlsx_buffer, index=False)
        xlsx_content = xlsx_buffer.getvalue()
        file_obj = io.BytesIO(xlsx_content)
        return storage.create_session("test.xlsx", file_obj, len(xlsx_content))

    def test_csv_reader_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2,col3\n1,2,3\n4,5,6\n7,8,9\n"
            session = self._create_csv_session(storage, content)
            reader = create_reader(session)

            preview = reader.get_preview(n_rows=2)

            assert preview["row_count"] == 2
            assert preview["columns"] == ["col1", "col2", "col3"]
            assert len(preview["rows"]) == 2
            assert preview["truncated"] is True

    def test_csv_reader_preview_with_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2,col3\n1,2,3\n4,5,6\n"
            session = self._create_csv_session(storage, content)
            reader = create_reader(session)

            preview = reader.get_preview(n_rows=10, columns=["col1", "col3"])

            assert preview["columns"] == ["col1", "col3"]
            assert all(set(r.keys()) == {"col1", "col3"} for r in preview["rows"])

    def test_csv_reader_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n" + b"\n".join(f"{i},{i*2}".encode() for i in range(100))
            session = self._create_csv_session(storage, content)
            reader = create_reader(session)

            sample = reader.get_sample(n_rows=10, random_state=42)

            assert sample["row_count"] == 10
            assert sample["total_rows"] == 100
            assert sample["columns"] == ["col1", "col2"]

    def test_csv_reader_column_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2,col3\n1,2,3\n"
            session = self._create_csv_session(storage, content)
            reader = create_reader(session)

            info = reader.get_column_info()

            assert info["columns"] == ["col1", "col2", "col3"]
            assert info["column_count"] == 3
            assert "col1" in info["dtypes"]

    def test_csv_reader_row_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n" + b"\n".join(f"{i},{i*2}".encode() for i in range(50))
            session = self._create_csv_session(storage, content)
            reader = create_reader(session)

            count = reader.get_row_count()

            assert count == 50

    def test_csv_chunked_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n" + b"\n".join(f"{i},{i*2}".encode() for i in range(25))
            session = self._create_csv_session(storage, content)
            reader = create_reader(session)

            chunks = reader.read_csv_chunked(chunk_size=10, max_chunks=3)

            assert len(chunks) == 3
            total_rows = sum(c["row_count"] for c in chunks)
            assert total_rows == 25

    def test_csv_chunked_with_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2,col3\n1,2,3\n4,5,6\n"
            session = self._create_csv_session(storage, content)
            reader = create_reader(session)

            chunks = reader.read_csv_chunked(chunk_size=10, columns=["col1", "col3"])

            assert len(chunks) == 1
            assert chunks[0]["columns"] == ["col1", "col3"]

    def test_xlsx_reader_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            session = self._create_xlsx_session(storage, {"a": [1, 2, 3], "b": [4, 5, 6]})
            reader = create_reader(session)

            preview = reader.get_preview(n_rows=2)

            assert preview["row_count"] == 2
            assert preview["columns"] == ["a", "b"]
            assert "sheet_name" in preview

    def test_xlsx_reader_sheet_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            import pandas as pd
            df1 = pd.DataFrame({"a": [1]})
            df2 = pd.DataFrame({"b": [2]})
            xlsx_buffer = io.BytesIO()
            with pd.ExcelWriter(xlsx_buffer) as writer:
                df1.to_excel(writer, sheet_name="Sheet1", index=False)
                df2.to_excel(writer, sheet_name="Sheet2", index=False)
            xlsx_content = xlsx_buffer.getvalue()

            file_obj = io.BytesIO(xlsx_content)
            session = storage.create_session("multi.xlsx", file_obj, len(xlsx_content))
            reader = create_reader(session)

            sheets = reader.get_sheet_names()

            assert "Sheet1" in sheets
            assert "Sheet2" in sheets

    def test_xlsx_reader_read_sheet_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            import pandas as pd
            df1 = pd.DataFrame({"a": [1, 2]})
            df2 = pd.DataFrame({"b": [3, 4]})
            xlsx_buffer = io.BytesIO()
            with pd.ExcelWriter(xlsx_buffer) as writer:
                df1.to_excel(writer, sheet_name="First", index=False)
                df2.to_excel(writer, sheet_name="Second", index=False)
            xlsx_content = xlsx_buffer.getvalue()

            file_obj = io.BytesIO(xlsx_content)
            session = storage.create_session("multi.xlsx", file_obj, len(xlsx_content))
            reader = create_reader(session)

            result = reader.read_sheet(sheet_name="Second", n_rows=10)

            assert result["sheet_name"] == "Second"
            assert result["columns"] == ["b"]
            assert result["row_count"] == 2

    def test_xlsx_reader_read_sheet_by_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            import pandas as pd
            df1 = pd.DataFrame({"a": [1]})
            df2 = pd.DataFrame({"b": [2]})
            xlsx_buffer = io.BytesIO()
            with pd.ExcelWriter(xlsx_buffer) as writer:
                df1.to_excel(writer, sheet_name="First", index=False)
                df2.to_excel(writer, sheet_name="Second", index=False)
            xlsx_content = xlsx_buffer.getvalue()

            file_obj = io.BytesIO(xlsx_content)
            session = storage.create_session("multi.xlsx", file_obj, len(xlsx_content))
            reader = create_reader(session)

            result = reader.read_sheet(sheet_name=1, n_rows=10)

            assert result["sheet_name"] == "Second"

    def test_mixed_missing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2,col3\n1,,3\n,5,\n7,8,\n"
            session = self._create_csv_session(storage, content)
            reader = create_reader(session)

            preview = reader.get_preview(n_rows=10)

            assert preview["row_count"] == 3
            assert preview["columns"] == ["col1", "col2", "col3"]

    def test_larger_csv_bounded_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n" + b"\n".join(f"{i},{i*2}".encode() for i in range(10000))
            session = self._create_csv_session(storage, content)
            reader = create_reader(session)

            preview = reader.get_preview(n_rows=100)
            assert preview["row_count"] == 100
            assert preview["truncated"] is True

            sample = reader.get_sample(n_rows=500, random_state=123)
            assert sample["row_count"] == 500
            assert sample["total_rows"] == 10000

    def test_csv_invalid_columns_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n1,2\n"
            session = self._create_csv_session(storage, content)
            reader = create_reader(session)

            with pytest.raises(ReaderError):
                reader.get_preview(columns=["nonexistent"])

    def test_reader_enforces_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)

            content = b"col1,col2\n1,2\n"
            session = self._create_csv_session(storage, content)
            reader = create_reader(session)

            with pytest.raises(ReaderError):
                reader.get_preview(n_rows=200)

            with pytest.raises(ReaderError):
                reader.get_sample(n_rows=2000)

    def test_xls_reader(self):
        pytest.skip("XLS format not supported (xlwt deprecated), use XLSX")


class TestSessionReaderIntegration:
    def test_manager_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n1,2\n3,4\n"
            file_obj = io.BytesIO(content)
            session = manager.create_session("test.csv", file_obj, len(content))

            preview = manager.preview_dataset(session.dataset_id, n_rows=2)

            assert preview["row_count"] == 2

    def test_manager_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n" + b"\n".join(f"{i},{i*2}".encode() for i in range(100))
            file_obj = io.BytesIO(content)
            session = manager.create_session("test.csv", file_obj, len(content))

            sample = manager.sample_dataset(session.dataset_id, n_rows=10, random_state=42)

            assert sample["row_count"] == 10
            assert sample["total_rows"] == 100

    def test_manager_list_sheets(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            import pandas as pd
            df = pd.DataFrame({"a": [1]})
            xlsx_buffer = io.BytesIO()
            df.to_excel(xlsx_buffer, index=False)
            xlsx_content = xlsx_buffer.getvalue()

            file_obj = io.BytesIO(xlsx_content)
            session = manager.create_session("test.xlsx", file_obj, len(xlsx_content))

            sheets = manager.list_sheets(session.dataset_id)

            assert len(sheets) >= 1

    def test_manager_read_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            import pandas as pd
            df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
            xlsx_buffer = io.BytesIO()
            df.to_excel(xlsx_buffer, index=False)
            xlsx_content = xlsx_buffer.getvalue()

            file_obj = io.BytesIO(xlsx_content)
            session = manager.create_session("test.xlsx", file_obj, len(xlsx_content))

            result = manager.read_sheet(session.dataset_id, sheet_name=0, n_rows=10)

            assert result["row_count"] == 2
            assert result["columns"] == ["a", "b"]

    def test_manager_column_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2,col3\n1,2,3\n"
            file_obj = io.BytesIO(content)
            session = manager.create_session("test.csv", file_obj, len(content))

            info = manager.get_column_info(session.dataset_id)

            assert info["columns"] == ["col1", "col2", "col3"]
            assert info["column_count"] == 3

    def test_manager_row_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n" + b"\n".join(f"{i},{i*2}".encode() for i in range(50))
            file_obj = io.BytesIO(content)
            session = manager.create_session("test.csv", file_obj, len(content))

            count = manager.get_row_count(session.dataset_id)

            assert count == 50

    def test_manager_chunked_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "test_storage"
            storage = DatasetStorage(base_path=base, ttl_seconds=3600)
            manager = SessionManager(storage=storage)

            content = b"col1,col2\n" + b"\n".join(f"{i},{i*2}".encode() for i in range(25))
            file_obj = io.BytesIO(content)
            session = manager.create_session("test.csv", file_obj, len(content))

            chunks = manager.read_csv_chunks(session.dataset_id, chunk_size=10, max_chunks=3)

            assert len(chunks) == 3
            total_rows = sum(c["row_count"] for c in chunks)
            assert total_rows == 25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])