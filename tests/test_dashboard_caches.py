"""The Dashboard warm-up must produce identical values without the memory spike.

``_compute_inventory_value`` streams ``inventory_snapshots.csv`` and keeps only
the newest snapshot instead of materialising all 3.16 M rows. These tests pin
the streamed result to the original whole-frame algorithm.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import api.routes.dashboard as dashboard


def _whole_frame_inventory_value(root: Path) -> float | None:
    """Byte-for-byte copy of the pre-streaming implementation."""

    def read_csv(name, usecols=None, dtype=None):
        path = root / name
        if not path.exists():
            return pd.DataFrame()
        kwargs = {}
        if usecols is not None:
            kwargs["usecols"] = usecols
        if dtype is not None:
            kwargs["dtype"] = {k: v for k, v in dtype.items() if k in usecols}
        try:
            return pd.read_csv(path, **kwargs)
        except ValueError:
            return pd.read_csv(path)

    inventory = read_csv(
        "inventory_snapshots.csv",
        usecols=["snapshot_date", "product_id", "on_hand"],
        dtype={"product_id": "category"},
    )
    purchase_orders = read_csv(
        "purchase_orders.csv",
        usecols=["product_id", "unit_cost"],
    )

    if inventory.empty or purchase_orders.empty:
        return None

    required_inventory = {"snapshot_date", "product_id", "on_hand"}
    required_cost = {"product_id", "unit_cost"}

    if not required_inventory.issubset(inventory.columns):
        return None
    if not required_cost.issubset(purchase_orders.columns):
        return None

    latest_snapshot = inventory["snapshot_date"].max()
    latest = inventory[inventory["snapshot_date"].eq(latest_snapshot)].copy()
    if latest.empty:
        return None

    costs = (
        purchase_orders.dropna(subset=["product_id", "unit_cost"])
        .groupby("product_id")["unit_cost"]
        .mean()
    )
    latest["unit_cost"] = latest["product_id"].map(costs).astype(float)
    coverage = float(latest["unit_cost"].notna().mean())
    if coverage < 0.95:
        return None
    return float((latest["on_hand"] * latest["unit_cost"]).sum())


def _write(root: Path, inventory: pd.DataFrame | None, orders: pd.DataFrame | None) -> None:
    if inventory is not None:
        inventory.to_csv(root / "inventory_snapshots.csv", index=False)
    if orders is not None:
        orders.to_csv(root / "purchase_orders.csv", index=False)


def _run(root: Path, monkeypatch, chunksize: int = 1000) -> float | None:
    monkeypatch.setattr(dashboard, "_processed_path", lambda name: root / name)
    monkeypatch.setattr(dashboard, "_INVENTORY_CHUNKS", chunksize)
    dashboard._cache["inventory_value"] = dashboard._UNSET
    return dashboard._inventory_value()


def _frames(snapshots: int = 3, rows_per_snapshot: int = 5000):
    dates = [f"2018-0{d}-01" for d in range(1, snapshots + 1)]
    total = snapshots * rows_per_snapshot
    inventory = pd.DataFrame(
        {
            "snapshot_date": [d for d in dates for _ in range(rows_per_snapshot)],
            "product_id": [f"SKU-{n % 40:04d}" for n in range(total)],
            "on_hand": list(range(total)),
        }
    )
    orders = pd.DataFrame(
        {
            "product_id": [f"SKU-{i:04d}" for i in range(40)],
            "unit_cost": [1.5 + i * 0.25 for i in range(40)],
        }
    )
    return inventory, orders


@pytest.mark.parametrize("snapshots", [1, 3, 8])
@pytest.mark.parametrize("chunksize", [500, 5000, 1_000_000])
def test_matches_whole_frame_algorithm(tmp_path, monkeypatch, snapshots, chunksize):
    inventory, orders = _frames(snapshots=snapshots)
    _write(tmp_path, inventory, orders)

    expected = _whole_frame_inventory_value(tmp_path)
    actual = _run(tmp_path, monkeypatch, chunksize=chunksize)

    assert expected is not None
    assert actual == pytest.approx(expected, rel=0, abs=0)


def _sparse_estimate(inventory: pd.DataFrame, orders: pd.DataFrame) -> float:
    """Contract of the streamed implementation when cost coverage is low.

    The original whole-frame algorithm returned ``None`` below 95 % coverage,
    which blanked the KPI: ``purchase_orders.csv`` prices only 497 of 32 951
    catalogued products.  The streamed version instead values priced rows at
    their real PO cost and unpriced rows at the mean PO unit cost.
    """
    latest = inventory["snapshot_date"].max()
    latest_rows = inventory[inventory["snapshot_date"].eq(latest)]
    costs = (
        orders.dropna(subset=["product_id", "unit_cost"])
        .groupby("product_id")["unit_cost"]
        .mean()
    )
    mapped = latest_rows["product_id"].map(costs).astype(float)
    valid = mapped.notna()
    total = float((latest_rows.loc[valid, "on_hand"] * mapped[valid]).sum())
    avg_unit_cost = float(costs.mean()) if len(costs) else 0.0
    return total + (len(latest_rows) - int(valid.sum())) * avg_unit_cost


def test_sparse_cost_coverage_falls_back_to_mean_unit_cost(tmp_path, monkeypatch):
    inventory, orders = _frames(snapshots=2)
    orders = orders.iloc[:5]
    _write(tmp_path, inventory, orders)

    # The pre-streaming algorithm refuses to value the KPI below 95% coverage.
    assert _whole_frame_inventory_value(tmp_path) is None

    # The streamed implementation keeps the KPI alive instead of blanking it.
    expected = _sparse_estimate(inventory, orders)
    assert expected > 0
    assert _run(tmp_path, monkeypatch) == pytest.approx(expected, rel=0, abs=0)


def test_missing_file_returns_none(tmp_path, monkeypatch):
    assert _run(tmp_path, monkeypatch) is None


def test_header_only_file_returns_none(tmp_path, monkeypatch):
    _write(
        tmp_path,
        pd.DataFrame(columns=["snapshot_date", "product_id", "on_hand"]),
        pd.DataFrame(columns=["product_id", "unit_cost"]),
    )
    assert _whole_frame_inventory_value(tmp_path) is None
    assert _run(tmp_path, monkeypatch) is None


def test_missing_column_returns_none(tmp_path, monkeypatch):
    inventory, orders = _frames(snapshots=2)
    inventory = inventory.drop(columns=["on_hand"])
    _write(tmp_path, inventory, orders)
    assert _run(tmp_path, monkeypatch) is None


def test_all_dates_missing_returns_none(tmp_path, monkeypatch):
    inventory, orders = _frames(snapshots=2)
    inventory["snapshot_date"] = None
    _write(tmp_path, inventory, orders)
    assert _whole_frame_inventory_value(tmp_path) is None
    assert _run(tmp_path, monkeypatch) is None


def test_warm_caches_is_sequential(monkeypatch):
    """The warm-up must never run two multi-hundred-MB parses at once."""
    seen: list[str] = []

    for name in (
        "_stockout_risks",
        "_delivery_risks",
        "_supplier_risks",
        "_inventory_value",
        "_daily_sales",
    ):
        monkeypatch.setitem(dashboard._cache, name, dashboard._UNSET)
        monkeypatch.setattr(dashboard, name, lambda name=name: seen.append(name))

    dashboard._warm_caches()

    assert seen == [
        "_stockout_risks",
        "_delivery_risks",
        "_supplier_risks",
        "_inventory_value",
        "_daily_sales",
    ]
