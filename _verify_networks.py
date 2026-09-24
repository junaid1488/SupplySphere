import sys
sys.path.insert(0, ".")

from geospatial.service import (
    warehouse_features,
    route_table,
    transfer_points,
    shipping_lanes,
    BRAZIL_NETWORK,
    INDIA_NETWORK,
    NETWORK,
)
from configs.settings import settings

# --- BRAZIL ---
b = warehouse_features()
assert len(b) == 15, len(b)
assert list(b["warehouse_id"]) == [f"WH-{i:03d}" for i in range(1, 16)]
assert list(b["city"]) == [
    "São Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba",
    "Porto Alegre", "Brasília", "Goiânia", "Salvador", "Recife",
    "Fortaleza", "Manaus", "Belém", "Campinas", "Ribeirão Preto", "Vitória",
]
assert list(b["state"]) == [
    "SP", "RJ", "MG", "PR", "RS", "DF", "GO", "BA", "PE",
    "CE", "AM", "PA", "SP", "SP", "ES",
]
assert list(zip(b["latitude"], b["longitude"])) == [
    (-23.5505, -46.6333), (-22.9068, -43.1729), (-19.9167, -43.9345),
    (-25.4284, -49.2733), (-30.0346, -51.2177), (-15.7939, -47.8828),
    (-16.6869, -49.2648), (-12.9777, -38.5016), (-8.0476, -34.877),
    (-3.7319, -38.5267), (-3.119, -60.0217), (-1.4558, -48.4902),
    (-22.9099, -47.0626), (-21.1704, -47.8103), (-20.3155, -40.3128),
]
assert len(route_table()) == 210
assert len(route_table("brazil")) == 210
tb = transfer_points(settings.processed_data_dir, limit=100000, network="brazil")
assert len(tb) == 445, len(tb)
assert len(BRAZIL_NETWORK) == 15
assert NETWORK is BRAZIL_NETWORK
assert len(INDIA_NETWORK) == 12

svc = open("geospatial/service.py", encoding="utf-8").read()
assert "São Paulo Hub" in svc and "Synthetic demo warehouse network" in svc

fe = open("frontend/src/OlistControlTower.tsx", encoding="utf-8").read()
assert "Warehouses · Synthetic Demo" in fe
assert "Synthetic Demo Warehouse" in fe
assert "Synthetic Warehouse Transfer" in fe
assert "Synthetic Warehouse Route" in fe
assert "Shipping Lane" in fe
assert "BRAZIL_BOUNDS" in fe
assert "React.useState<NetworkName>('brazil')" in fe
assert "fitBounds(\n      BRAZIL_BOUNDS,\n      brazilViewOptions,\n    )" in fe

# --- INDIA ---
i = warehouse_features("india")
assert len(i) == 12, len(i)
assert list(i["city"]) == [
    "Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Chennai", "Kolkata",
    "Lucknow", "Jaipur", "Pune", "Ahmedabad", "Patna", "Guwahati",
]
assert list(i["warehouse_id"]) == [f"WH-{n:03d}" for n in range(1, 13)]
ri = route_table("india")
assert len(ri) == 132, len(ri)
assert (ri["origin_warehouse_id"] != ri["destination_warehouse_id"]).all()
ti = transfer_points(settings.processed_data_dir, limit=100000, network="india")
assert len(ti) == 445, len(ti)

# --- SHIPPING LANES ---
_, total = shipping_lanes(settings.raw_data_dir, return_total=True)
assert total == 112096, total

print("BRAZIL: wh=15 routes=210 transfers=445 labels=PASS bounds=PASS default=brazil")
print("INDIA: wh=12 routes=132 transfers=445 cities=PASS")
print("SHIPPING: total=112096")
print("ALL VERIFICATION CHECKS PASS")
