from collections import OrderedDict
import gc
import threading

from fastapi import APIRouter, Query
from configs.settings import settings
from geospatial.service import (
    warehouse_features,
    customer_points,
    seller_points,
    route_table,
    order_points,
    demand_points,
    inventory_points,
    delivery_points,
    transfer_points,
    shipping_lanes,
)

router = APIRouter(prefix="/api/geospatial", tags=["geospatial"])

# The map fires every layer at once; each builder materialises a 100k-row frame
# (up to 56 MB), so concurrent first loads peaked near the 512 MiB Render limit
# and returned 502s.  Two guards fix it: only two builders may run at a time
# (bounds the transient peak to ~112 MB) and the finished response payload is
# cached (small - just the requested rows) so repeats never rebuild anything.
_PAYLOAD_CACHE: OrderedDict[tuple, dict] = OrderedDict()
_CACHE_LIMIT = 64
_CACHE_LOCK = threading.Lock()
_BUILD_LOCKS: dict[tuple, threading.Lock] = {}
_BUILD_SLOTS = threading.Semaphore(2)


def records(df, limit, offset):
    total = len(df)
    df = df.iloc[offset : offset + limit]
    return {
        "items": df.where(df.notna(), None).to_dict("records"),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _cached_records(key: str, builder, limit: int, offset: int) -> dict:
    cache_key = (key, limit, offset)
    with _CACHE_LOCK:
        hit = _PAYLOAD_CACHE.get(cache_key)
        if hit is not None:
            _PAYLOAD_CACHE.move_to_end(cache_key)
            return hit
        build_lock = _BUILD_LOCKS.setdefault(cache_key, threading.Lock())
    with build_lock:
        with _CACHE_LOCK:
            hit = _PAYLOAD_CACHE.get(cache_key)
            if hit is not None:
                _PAYLOAD_CACHE.move_to_end(cache_key)
                return hit
        with _BUILD_SLOTS:
            df = builder()
        payload = records(df, limit, offset)
        del df
        gc.collect()
        with _CACHE_LOCK:
            _PAYLOAD_CACHE[cache_key] = payload
            _PAYLOAD_CACHE.move_to_end(cache_key)
            while len(_PAYLOAD_CACHE) > _CACHE_LIMIT:
                _PAYLOAD_CACHE.popitem(last=False)
        return payload


@router.get("/warehouses")
def warehouses(
    network: str = Query("brazil", pattern="^(brazil|india)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return _cached_records(
        f"warehouses:{network}", lambda: warehouse_features(network), limit, offset
    )


@router.get("/customers")
def customers(limit: int = Query(100, ge=1, le=10000), offset: int = Query(0, ge=0)):
    return _cached_records(
        "customers",
        lambda: customer_points(settings.raw_data_dir, limit=100000),
        limit,
        offset,
    )


@router.get("/sellers")
def sellers(limit: int = Query(100, ge=1, le=5000), offset: int = Query(0, ge=0)):
    return _cached_records(
        "sellers",
        lambda: seller_points(settings.raw_data_dir, limit=100000),
        limit,
        offset,
    )


@router.get("/orders")
def orders(limit: int = Query(100, ge=1, le=10000), offset: int = Query(0, ge=0)):
    return _cached_records(
        "orders",
        lambda: order_points(settings.raw_data_dir, limit=100000),
        limit,
        offset,
    )


@router.get("/demand")
def demand(limit: int = Query(100, ge=1, le=5000), offset: int = Query(0, ge=0)):
    return _cached_records(
        "demand",
        lambda: demand_points(
            str(settings.processed_data_dir), str(settings.raw_data_dir), limit=100000
        ),
        limit,
        offset,
    )


@router.get("/inventory")
def inventory(limit: int = Query(100, ge=1, le=5000), offset: int = Query(0, ge=0)):
    return _cached_records(
        "inventory",
        lambda: inventory_points(str(settings.processed_data_dir), limit=100000),
        limit,
        offset,
    )


@router.get("/delivery")
def delivery(limit: int = Query(100, ge=1, le=10000), offset: int = Query(0, ge=0)):
    return _cached_records(
        "delivery",
        lambda: delivery_points(
            str(settings.raw_data_dir), str(settings.processed_data_dir), limit=100000
        ),
        limit,
        offset,
    )


@router.get("/transfers")
def transfers(
    network: str = Query("brazil", pattern="^(brazil|india)$"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    return _cached_records(
        f"transfers:{network}",
        lambda: transfer_points(
            settings.processed_data_dir, limit=100000, network=network
        ),
        limit,
        offset,
    )


@router.get("/shipping-lanes")
def shipping_lanes_endpoint(
    limit: int = Query(100, ge=1, le=5000), offset: int = Query(0, ge=0)
):
    return _cached_records(
        "shipping-lanes", lambda: shipping_lanes(settings.raw_data_dir), limit, offset
    )


@router.get("/routes")
def routes(network: str = Query("brazil", pattern="^(brazil|india)$")):
    payload = _cached_records(f"routes:{network}", lambda: route_table(network), 10_000, 0)
    return {**payload, "network": network}
