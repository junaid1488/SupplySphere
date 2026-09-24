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


def records(df, limit, offset):
    total = len(df)
    df = df.iloc[offset : offset + limit]
    return {
        "items": df.where(df.notna(), None).to_dict("records"),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/warehouses")
def warehouses(
    network: str = Query("brazil", pattern="^(brazil|india)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return records(warehouse_features(network), limit, offset)


@router.get("/customers")
def customers(limit: int = Query(100, ge=1, le=10000), offset: int = Query(0, ge=0)):
    return records(customer_points(settings.raw_data_dir, limit=100000), limit, offset)


@router.get("/sellers")
def sellers(limit: int = Query(100, ge=1, le=5000), offset: int = Query(0, ge=0)):
    return records(seller_points(settings.raw_data_dir, limit=100000), limit, offset)


@router.get("/orders")
def orders(limit: int = Query(100, ge=1, le=10000), offset: int = Query(0, ge=0)):
    return records(order_points(settings.raw_data_dir, limit=100000), limit, offset)


@router.get("/demand")
def demand(limit: int = Query(100, ge=1, le=5000), offset: int = Query(0, ge=0)):
    return records(
        demand_points(str(settings.processed_data_dir), str(settings.raw_data_dir), limit=100000),
        limit,
        offset,
    )


@router.get("/inventory")
def inventory(limit: int = Query(100, ge=1, le=5000), offset: int = Query(0, ge=0)):
    return records(
        inventory_points(str(settings.processed_data_dir), limit=100000), limit, offset
    )


@router.get("/delivery")
def delivery(limit: int = Query(100, ge=1, le=10000), offset: int = Query(0, ge=0)):
    return records(
        delivery_points(str(settings.raw_data_dir), str(settings.processed_data_dir), limit=100000),
        limit,
        offset,
    )


@router.get("/transfers")
def transfers(
    network: str = Query("brazil", pattern="^(brazil|india)$"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    return records(
        transfer_points(settings.processed_data_dir, limit=100000, network=network),
        limit,
        offset,
    )


@router.get("/shipping-lanes")
def shipping_lanes_endpoint(
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    return records(shipping_lanes(settings.raw_data_dir), limit, offset)


@router.get("/routes")
def routes(network: str = Query("brazil", pattern="^(brazil|india)$")):
    table = route_table(network)
    return {"items": table.to_dict("records"), "total": int(len(table)), "network": network}
