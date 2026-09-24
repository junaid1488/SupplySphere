from __future__ import annotations
from pathlib import Path
import hashlib
import os
import shutil
import tempfile
from typing import BinaryIO

from dataset_analyzer.models import DatasetMetadata, DatasetSession, FileFormat, generate_dataset_id


class StorageError(Exception):
    pass


class PathSafetyError(StorageError):
    pass


class ContentValidationError(StorageError):
    pass


class FileSizeLimitError(StorageError):
    pass


class EmptyFileError(StorageError):
    pass


class DatasetStorage:
    DEFAULT_MAX_FILE_SIZE = 500 * 1024 * 1024
    CHUNK_SIZE = 8192

    XLSX_MAGIC = b"PK\x03\x04"
    XLS_MAGIC = b"\xd0\xcf\x11\xe0"

    def __init__(
        self,
        base_path: Path | None = None,
        ttl_seconds: int = 3600,
        max_file_size: int | None = None,
    ):
        if base_path is None:
            base_path = Path(tempfile.gettempdir()) / "supplysphere_dataset_analyzer"
        self.base_path = base_path.resolve()
        self.ttl_seconds = ttl_seconds
        self.max_file_size = max_file_size or self.DEFAULT_MAX_FILE_SIZE
        self._ensure_base_path()

    def _ensure_base_path(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        if not os.access(self.base_path, os.W_OK | os.X_OK):
            raise StorageError(f"Base path not writable: {self.base_path}")

    def _validate_dataset_id(self, dataset_id: str) -> None:
        if not dataset_id or not dataset_id.startswith("ds_"):
            raise PathSafetyError(f"Invalid dataset_id format: {dataset_id}")
        if ".." in dataset_id or "/" in dataset_id or "\\" in dataset_id:
            raise PathSafetyError(f"Path traversal attempt in dataset_id: {dataset_id}")

    def _get_dataset_dir(self, dataset_id: str) -> Path:
        self._validate_dataset_id(dataset_id)
        dataset_dir = (self.base_path / dataset_id).resolve()
        try:
            dataset_dir.relative_to(self.base_path)
        except ValueError:
            raise PathSafetyError(f"Dataset path escapes base directory: {dataset_id}")
        return dataset_dir

    def _compute_hash_streaming(self, file_obj: BinaryIO) -> tuple[str, int]:
        hasher = hashlib.sha256()
        total_bytes = 0
        for chunk in iter(lambda: file_obj.read(self.CHUNK_SIZE), b""):
            hasher.update(chunk)
            total_bytes += len(chunk)
        file_obj.seek(0)
        return hasher.hexdigest()[:32], total_bytes

    def _detect_format(self, filename: str) -> FileFormat:
        ext = Path(filename).suffix.lower()
        if ext == ".csv":
            return FileFormat.CSV
        if ext == ".xls":
            return FileFormat.XLS
        if ext == ".xlsx":
            return FileFormat.XLSX
        raise StorageError(f"Unsupported file format: {ext}")

    def _validate_content(self, file_obj: BinaryIO, file_format: FileFormat) -> None:
        header = file_obj.read(8192)
        file_obj.seek(0)

        if not header:
            raise EmptyFileError("File is empty")

        if file_format == FileFormat.XLSX:
            if not header.startswith(self.XLSX_MAGIC):
                raise ContentValidationError("File does not appear to be a valid XLSX (missing PK header)")
        elif file_format == FileFormat.XLS:
            if not header.startswith(self.XLS_MAGIC):
                raise ContentValidationError("File does not appear to be a valid XLS (missing OLE header)")
        elif file_format == FileFormat.CSV:
            if not self._looks_like_csv(header):
                raise ContentValidationError("File does not appear to be a valid CSV")

    def _looks_like_csv(self, header: bytes) -> bool:
        try:
            text = header.decode("utf-8", errors="ignore")
        except Exception:
            return False

        lines = text.strip().splitlines()
        if not lines:
            return False

        first_line = lines[0].strip()
        if not first_line:
            return False

        delimiter_counts = {
            ",": first_line.count(","),
            ";": first_line.count(";"),
            "\t": first_line.count("\t"),
            "|": first_line.count("|"),
        }

        max_delim = max(delimiter_counts.values())
        if max_delim == 0:
            return len(lines) > 1

        return True

    def _stream_to_file(
        self,
        file_obj: BinaryIO,
        storage_path: Path,
        max_size: int,
    ) -> int:
        total_written = 0
        with storage_path.open("wb") as f:
            for chunk in iter(lambda: file_obj.read(self.CHUNK_SIZE), b""):
                total_written += len(chunk)
                if total_written > max_size:
                    raise FileSizeLimitError(f"File size exceeds maximum allowed: {max_size} bytes")
                f.write(chunk)
        return total_written

    def create_session(
        self,
        original_filename: str,
        file_obj: BinaryIO,
        declared_size: int | None = None,
    ) -> DatasetSession:
        if declared_size is not None and declared_size > self.max_file_size:
            raise FileSizeLimitError(f"Declared file size {declared_size} exceeds maximum {self.max_file_size}")

        dataset_id = generate_dataset_id()
        file_format = self._detect_format(original_filename)

        content_hash, actual_size = self._compute_hash_streaming(file_obj)

        if actual_size == 0:
            raise EmptyFileError("File is empty")

        if actual_size > self.max_file_size:
            raise FileSizeLimitError(f"File size {actual_size} exceeds maximum {self.max_file_size}")

        if declared_size is not None and actual_size != declared_size:
            raise StorageError(f"File size mismatch: declared {declared_size}, actual {actual_size}")

        self._validate_content(file_obj, file_format)

        dataset_dir = self._get_dataset_dir(dataset_id)
        dataset_dir.mkdir(parents=True, exist_ok=False)

        safe_filename = f"data{Path(original_filename).suffix.lower()}"
        storage_path = dataset_dir / safe_filename

        try:
            written_size = self._stream_to_file(file_obj, storage_path, self.max_file_size)
        except Exception:
            if dataset_dir.exists():
                shutil.rmtree(dataset_dir, ignore_errors=True)
            raise

        if written_size != actual_size:
            shutil.rmtree(dataset_dir, ignore_errors=True)
            raise StorageError(f"Write size mismatch: expected {actual_size}, wrote {written_size}")

        from datetime import datetime, timedelta
        now = datetime.utcnow()
        metadata = DatasetMetadata(
            dataset_id=dataset_id,
            original_filename=original_filename,
            file_format=file_format,
            file_size_bytes=written_size,
            content_hash=content_hash,
            created_at=now,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
        )

        metadata_path = dataset_dir / "metadata.json"
        metadata_path.write_text(__import__("json").dumps(metadata.to_dict(), indent=2))

        return DatasetSession(metadata=metadata, storage_path=storage_path)

    def get_session(self, dataset_id: str) -> DatasetSession | None:
        self._validate_dataset_id(dataset_id)
        dataset_dir = self._get_dataset_dir(dataset_id)
        if not dataset_dir.exists():
            return None

        metadata_path = dataset_dir / "metadata.json"
        if not metadata_path.exists():
            return None

        import json
        metadata_dict = json.loads(metadata_path.read_text())
        metadata = DatasetMetadata.from_dict(metadata_dict)

        data_files = list(dataset_dir.glob("data.*"))
        if not data_files:
            return None

        return DatasetSession(metadata=metadata, storage_path=data_files[0])

    def update_metadata(self, dataset_id: str, **updates: dict[str, any]) -> DatasetMetadata:
        session = self.get_session(dataset_id)
        if session is None:
            raise StorageError(f"Dataset not found: {dataset_id}")

        metadata_dict = session.metadata.to_dict()
        metadata_dict.update(updates)
        new_metadata = DatasetMetadata.from_dict(metadata_dict)

        dataset_dir = self._get_dataset_dir(dataset_id)
        metadata_path = dataset_dir / "metadata.json"
        metadata_path.write_text(__import__("json").dumps(new_metadata.to_dict(), indent=2))

        return new_metadata

    def delete_session(self, dataset_id: str) -> bool:
        self._validate_dataset_id(dataset_id)
        dataset_dir = self._get_dataset_dir(dataset_id)
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir)
            return True
        return False

    def cleanup_expired(self) -> int:
        count = 0
        for dataset_dir in self.base_path.iterdir():
            if not dataset_dir.is_dir():
                continue
            metadata_path = dataset_dir / "metadata.json"
            if not metadata_path.exists():
                continue
            try:
                import json
                from datetime import datetime
                metadata_dict = json.loads(metadata_path.read_text())
                expires_at = datetime.fromisoformat(metadata_dict["expires_at"])
                if datetime.utcnow() > expires_at:
                    shutil.rmtree(dataset_dir)
                    count += 1
            except Exception:
                continue
        return count

    def list_sessions(self) -> list[DatasetMetadata]:
        sessions = []
        for dataset_dir in self.base_path.iterdir():
            if not dataset_dir.is_dir():
                continue
            metadata_path = dataset_dir / "metadata.json"
            if not metadata_path.exists():
                continue
            try:
                import json
                metadata_dict = json.loads(metadata_path.read_text())
                sessions.append(DatasetMetadata.from_dict(metadata_dict))
            except Exception:
                continue
        return sessions