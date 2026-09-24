"""Package the verified SupplySphere runtime payload into a tar.gz archive.

Source roots (read-only):
  data/raw, data/processed, ml/models, data/models

The archive is written OUTSIDE the Git repository by default.
Source data is never modified or deleted.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE_ROOTS = (
    Path("data/raw"),
    Path("data/processed"),
    Path("ml/models"),
    Path("data/models"),
)

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "node_modules",
    "dist",
    ".git",
}

EXCLUDE_FILE_SUFFIXES = (
    ".log",
    ".err",
    ".pyc",
    ".pyo",
)

REQUIRED_FILES = (
    # raw (official Olist)
    "data/raw/olist_customers_dataset.csv",
    "data/raw/olist_geolocation_dataset.csv",
    "data/raw/olist_order_items_dataset.csv",
    "data/raw/olist_order_payments_dataset.csv",
    "data/raw/olist_order_reviews_dataset.csv",
    "data/raw/olist_orders_dataset.csv",
    "data/raw/olist_products_dataset.csv",
    "data/raw/olist_sellers_dataset.csv",
    "data/raw/product_category_name_translation.csv",
    # processed (API runtime)
    "data/processed/stockout_features.csv",
    "data/processed/stockout_predictions.csv",
    "data/processed/inventory_snapshots.csv",
    "data/processed/delivery_risk_features.csv",
    "data/processed/delivery_risk_predictions.csv",
    "data/processed/recommended_inventory_by_warehouse.csv",
    "data/processed/daily_product_demand.csv",
    "data/processed/daily_sales.csv",
    "data/processed/purchase_orders.csv",
    "data/processed/optimization_transfers.csv",
    "data/processed/optimization_supplier_quantities.csv",
    "data/processed/optimization_warehouse_quantities.csv",
    "data/processed/supplier_intelligence.csv",
    "data/processed/supplier_products.csv",
    "data/processed/suppliers.csv",
    "data/processed/shipment_events.csv",
    "data/processed/warehouses.csv",
    "data/processed/warehouse_metrics.csv",
    "data/processed/warehouse_transfers.csv",
    "data/processed/warehouse_transfer_recommendations.csv",
    "data/processed/stockout_shap_global.csv",
    "data/processed/phase10_summary.json",
    "data/processed/phase6_10_summary.json",
    "data/processed/phase9_summary.json",
    "data/processed/phase11_14_audit.json",
    "data/processed/phase15_17_audit.json",
    # models
    "ml/models/demand_forecast.joblib",
    "ml/models/stockout_model.joblib",
    "ml/models/delivery_risk_model.joblib",
    "data/models/stockout/stockout_model.joblib",
)


def _is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIR_NAMES:
        return True
    name = path.name
    if name.endswith(EXCLUDE_FILE_SUFFIXES):
        return True
    if name.startswith("._"):
        return True
    return False


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for rel_root in SOURCE_ROOTS:
        base = root / rel_root
        if not base.is_dir():
            raise FileNotFoundError(f"Required source directory missing: {base}")
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if _is_excluded(rel):
                continue
            files.append(path)
    return files


def verify_required(root: Path) -> None:
    missing = [rel for rel in REQUIRED_FILES if not (root / rel).is_file()]
    empty = [
        rel
        for rel in REQUIRED_FILES
        if (root / rel).is_file() and (root / rel).stat().st_size == 0
        and Path(rel).name != ".gitkeep"
    ]
    # product_category can be tiny but non-zero; empty only if 0 bytes
    empty = [rel for rel in empty if (root / rel).stat().st_size == 0]
    if missing or empty:
        lines = ["Runtime payload verification failed:"]
        for rel in missing:
            lines.append(f"  MISSING: {rel}")
        for rel in empty:
            lines.append(f"  EMPTY: {rel}")
        raise SystemExit("\n".join(lines))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package(root: Path, out_path: Path) -> dict[str, object]:
    verify_required(root)
    files = collect_files(root)
    if not files:
        raise SystemExit("No files found to package.")

    source_bytes = sum(path.stat().st_size for path in files)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    with tarfile.open(out_path, "w:gz") as tar:
        for path in files:
            tar.add(path, arcname=path.relative_to(root).as_posix())

    archive_bytes = out_path.stat().st_size
    checksum = sha256_file(out_path)
    return {
        "file_count": len(files),
        "source_bytes": source_bytes,
        "archive_bytes": archive_bytes,
        "archive_path": str(out_path),
        "sha256": checksum,
    }


def default_out_path() -> Path:
    # Outside the Git repository by default.
    return Path.home() / "SupplySphereArtifacts" / "supplysphere-runtime.tar.gz"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package SupplySphere runtime payload")
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Project root (default: repository root)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output tar.gz path (default: ~/SupplySphereArtifacts/supplysphere-runtime.tar.gz)",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    out_path = (args.out or default_out_path()).resolve()

    repo_root = root.resolve()
    try:
        out_path.relative_to(repo_root)
    except ValueError:
        pass
    else:
        raise SystemExit(
            f"Refusing to write archive inside the Git repository: {out_path}"
        )

    print(f"Root: {root}")
    print(f"Output: {out_path}")
    print("Verifying required runtime files...")
    result = package(root, out_path)
    print(f"File count: {result['file_count']}")
    print(f"Source size: {result['source_bytes']} bytes")
    print(f"Archive size: {result['archive_bytes']} bytes")
    print(f"SHA256: {result['sha256']}")
    print(f"Archive path: {result['archive_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
