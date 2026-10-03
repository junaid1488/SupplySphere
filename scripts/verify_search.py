"""Prove /api/search refactor keeps identical results to the original algorithm."""
from __future__ import annotations

import sys
import time

import pandas as pd

sys.path.insert(0, ".")
sys.path.insert(0, "src")

from api.services.data import (  # noqa: E402
    DataRepository,
    _STOCKOUT_CHUNKSIZE,
    _STOCKOUT_DTYPES,
    _match_mask,
)

QUERIES = [
    "zzz",
    "delhi",
    "WH-001",
    "critical",
    "high",
    "SUP-0007",
    "mumbai",
    "a",
    "de68fdc66141ead95fd569f01245e523",
]


def original_search(repo: DataRepository, q: str) -> list[dict]:
    """Byte-for-byte copy of the pre-refactor search implementation."""
    q = q.lower().strip()
    out = []
    for name, kind, cols, usecols, dtypes in [
        ('stockout_predictions.csv', 'SKU', ['product_id', 'warehouse_id', 'risk_level'], ['product_id', 'warehouse_id', 'risk_level'], _STOCKOUT_DTYPES),
        ('supplier_intelligence.csv', 'Supplier', ['supplier_id', 'supplier_name', 'risk_level'], ['supplier_id', 'supplier_name', 'risk_level'], None),
        ('warehouses.csv', 'Warehouse', ['warehouse_id', 'city'], ['warehouse_id', 'city'], None),
        ('delivery_risk_predictions.csv', 'Shipment', ['order_id', 'risk_level'], ['order_id', 'risk_level'], None),
    ]:
        dtype = {k: v for k, v in dtypes.items() if k in usecols} if dtypes else None
        if name == 'stockout_predictions.csv':
            path = repo.root / name
            if not path.exists():
                continue
            found = 0
            try:
                for chunk in pd.read_csv(path, usecols=usecols, dtype=dtype, chunksize=_STOCKOUT_CHUNKSIZE):
                    mask = pd.Series(False, index=chunk.index)
                    for c in cols:
                        if c in chunk:
                            mask |= _match_mask(chunk[c], q)
                    for r in chunk[mask].head(20 - found).to_dict('records'):
                        rid = str(r.get(cols[0], ''))
                        out.append({'type': kind, 'id': rid, 'label': rid, 'status': r.get('status'), 'risk_level': r.get('risk_level')})
                        found += 1
                    del chunk
                    if found >= 20:
                        break
            except Exception:
                pass
            continue
        df = repo._read(name, usecols=usecols, dtype=dtype)
        if df.empty:
            continue
        mask = pd.Series(False, index=df.index)
        for c in cols:
            if c in df:
                mask |= _match_mask(df[c], q)
        for r in df[mask].head(20).to_dict('records'):
            rid = str(r.get(cols[0], ''))
            out.append({'type': kind, 'id': rid, 'label': rid, 'status': r.get('status'), 'risk_level': r.get('risk_level')})
    return out


def main() -> None:
    repo = DataRepository()
    from api.services import data as data_module

    failures = 0
    for pass_label, prepare in (
        ("cold (no search domains)", lambda: None),
        ("warm (risk + warehouse domains known)", _prepare_domains),
    ):
        print(f"=== pass: {pass_label} ===")
        prepare()
        for q in QUERIES:
            data_module._SEARCH_CACHE.clear()
            t0 = time.time()
            expected = original_search(repo, q)
            old_s = time.time() - t0

            t0 = time.time()
            actual = repo.search(q)
            new_s = time.time() - t0

            ok = expected == actual
            if not ok:
                failures += 1
            print(
                f"  {'PASS' if ok else 'FAIL'} q={q!r}: {len(actual)} results | "
                f"old {old_s:.2f}s -> new {new_s:.2f}s"
            )
            if not ok:
                print("    expected[:3]:", expected[:3])
                print("    actual[:3]  :", actual[:3])

            t0 = time.time()
            again = repo.search(q)
            cached_s = time.time() - t0
            if again != expected:
                failures += 1
                print(f"    FAIL cached repeat for {q!r}")
            else:
                print(f"    cached repeat: {len(again)} results in {cached_s * 1000:.1f} ms")

    print("ALL PASS" if failures == 0 else f"{failures} FAILURES")
    sys.exit(1 if failures else 0)


def _prepare_domains() -> None:
    """Populate the exact value domains the pruned search path relies on."""
    from api.services import data as data_module

    repo = DataRepository()
    repo.stockout_risk_totals()
    repo.stockout_risk_counts()
    repo._warehouse_search_domain()
    print(
        "  domains: risk=",
        sorted(data_module._DERIVED_CACHE.get("stockout_risk_levels", [])),
        "| warehouse=",
        data_module._DERIVED_CACHE.get("warehouse_search_domain"),
    )


if __name__ == "__main__":
    main()
