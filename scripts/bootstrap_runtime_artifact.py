"""Download and safely extract the SupplySphere runtime artifact.

Intended for Render buildCommand (not per-request, not API startup).

Environment:
  SUPPLYSPHERE_RUNTIME_ARTIFACT_URL    Required unless payload already present.
  SUPPLYSPHERE_RUNTIME_ARTIFACT_SHA256 Optional checksum verification.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.package_runtime_artifact import REQUIRED_FILES, verify_required

URL_ENV = "SUPPLYSPHERE_RUNTIME_ARTIFACT_URL"
SHA_ENV = "SUPPLYSPHERE_RUNTIME_ARTIFACT_SHA256"
CHUNK = 1024 * 1024


def payload_complete(root: Path) -> bool:
    try:
        verify_required(root)
    except SystemExit:
        return False
    return True


def _normalize_member_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    # Strip only a leading "./" prefix (not character-class lstrip, which
    # would also eat "../" and absolute "/" markers before safety checks).
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_unsafe_member(name: str) -> bool:
    # Check the raw name first so ../ and absolute paths cannot hide
    # behind normalization.
    raw = name.replace("\\", "/")
    if raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
        return True
    if raw.startswith("../") or raw == ".." or "/../" in f"/{raw}/":
        return True
    if raw.startswith("~"):
        return True

    normalized = _normalize_member_name(name)
    if not normalized or normalized in {".", "./"}:
        return False
    if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
        return True
    if normalized.startswith("../") or normalized == ".." or "/../" in f"/{normalized}/":
        return True
    if normalized.startswith("~"):
        return True
    return False


def safe_extract_tar_gz(archive_path: Path, dest_root: Path) -> int:
    dest_root = dest_root.resolve()
    extracted = 0
    with tarfile.open(archive_path, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            if is_unsafe_member(member.name):
                raise SystemExit(
                    f"Unsafe archive member rejected: {member.name!r}"
                )
            if member.issym() or member.islnk():
                raise SystemExit(
                    f"Links are not allowed in runtime artifact: {member.name!r}"
                )
            if not (member.isfile() or member.isdir()):
                raise SystemExit(
                    f"Unsupported archive member type: {member.name!r}"
                )

            target = (dest_root / _normalize_member_name(member.name)).resolve()
            try:
                target.relative_to(dest_root)
            except ValueError as exc:
                raise SystemExit(
                    f"Path traversal blocked for member: {member.name!r}"
                ) from exc

        for member in members:
            if is_unsafe_member(member.name):
                raise SystemExit(f"Unsafe archive member rejected: {member.name!r}")
            target = (dest_root / _normalize_member_name(member.name)).resolve()
            try:
                target.relative_to(dest_root)
            except ValueError as exc:
                raise SystemExit(
                    f"Path traversal blocked for member: {member.name!r}"
                ) from exc
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                raise SystemExit(f"Failed to read member: {member.name!r}")
            with source, target.open("wb") as out:
                while True:
                    chunk = source.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
            extracted += 1
    return extracted


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dest: Path) -> None:
    print(f"Downloading runtime artifact from configured URL...")
    request = urllib.request.Request(url, headers={"User-Agent": "supplysphere-bootstrap/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=600) as response, dest.open("wb") as out:
            total = 0
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                total += len(chunk)
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to download runtime artifact: {exc}") from exc
    print(f"Downloaded {total} bytes")


def main() -> int:
    root = ROOT
    url = os.getenv(URL_ENV, "").strip()
    expected_sha = os.getenv(SHA_ENV, "").strip().lower()

    if not url:
        if payload_complete(root):
            print("Runtime payload already present; artifact URL not set.")
            print("Skipping download.")
            return 0
        missing = [rel for rel in REQUIRED_FILES if not (root / rel).is_file()]
        lines = [
            f"{URL_ENV} is not set and runtime payload is incomplete.",
            "Set SUPPLYSPHERE_RUNTIME_ARTIFACT_URL to a tar.gz containing:",
        ]
        lines.extend(f"  - {rel}" for rel in missing[:20])
        if len(missing) > 20:
            lines.append(f"  ... and {len(missing) - 20} more")
        raise SystemExit("\n".join(lines))

    if payload_complete(root) and os.getenv("SUPPLYSPHERE_RUNTIME_ARTIFACT_FORCE") != "1":
        print("Runtime payload already complete; skipping artifact download.")
        print("Set SUPPLYSPHERE_RUNTIME_ARTIFACT_FORCE=1 to force re-download.")
        return 0

    with tempfile.TemporaryDirectory(prefix="supplysphere-artifact-") as tmp:
        archive_path = Path(tmp) / "supplysphere-runtime.tar.gz"
        download(url, archive_path)

        if expected_sha:
            actual = sha256_file(archive_path)
            if actual != expected_sha:
                raise SystemExit(
                    "Checksum mismatch for runtime artifact.\n"
                    f"  expected: {expected_sha}\n"
                    f"  actual:   {actual}"
                )
            print(f"Checksum verified: {actual}")
        else:
            print("Checksum env not set; skipping SHA256 verification.")

        print("Extracting runtime artifact...")
        count = safe_extract_tar_gz(archive_path, root)
        print(f"Extracted files: {count}")

    print("Verifying required runtime files...")
    verify_required(root)
    print("Runtime artifact bootstrap complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
