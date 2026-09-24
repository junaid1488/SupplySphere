"""Download and validate the official Olist Brazilian E-Commerce dataset from Kaggle.

Authentication is handled by the Kaggle CLI. Set KAGGLE_API_TOKEN or place
Kaggle credentials in the standard ~/.kaggle location before running this script.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATASET = "olistbr/brazilian-ecommerce"
REQUIRED_FILES = (
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    raw = root / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)

    missing_before = [f for f in REQUIRED_FILES if not (raw / f).exists()]
    if not missing_before:
        print("Olist dataset already present and complete.")
        return 0

    command = [
        "kaggle", "datasets", "download", "-d", DATASET,
        "-p", str(raw), "--unzip", "--force",
    ]
    print(f"Downloading {DATASET} into {raw} ...")
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        print("ERROR: Kaggle CLI is not installed. Run: pip install kaggle")
        return 2
    except subprocess.CalledProcessError as exc:
        print("ERROR: Kaggle download failed.")
        print("Authenticate with Kaggle (KAGGLE_API_TOKEN or ~/.kaggle/kaggle.json) and retry.")
        return exc.returncode or 1

    # Kaggle may leave the downloaded archive behind; raw/ should contain source CSVs only.
    for archive in raw.glob("*.zip"):
        archive.unlink(missing_ok=True)

    missing = [f for f in REQUIRED_FILES if not (raw / f).is_file()]
    if missing:
        print("ERROR: Download completed but expected files are missing:")
        for name in missing:
            print(f"  - {name}")
        return 3

    print("Validated Olist source files:")
    for name in REQUIRED_FILES:
        print(f"  OK {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
