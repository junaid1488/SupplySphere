import pandas as pd

from src.synthetic.generator import SyntheticGenerator


def test_supplier_and_inventory():
    generator = SyntheticGenerator(42)

    products = pd.DataFrame(
        {
            "product_id": ["p1", "p2"],
        }
    )

    warehouses = generator.warehouses(2)
    suppliers = generator.suppliers(3)

    demand = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2018-08-01",
                    "2018-08-01",
                    "2018-08-02",
                    "2018-08-02",
                ]
            ),
            "product_id": [
                "p1",
                "p2",
                "p1",
                "p2",
            ],
            "demand": [
                10.0,
                8.0,
                12.0,
                9.0,
            ],
        }
    )

    inventory = generator.inventory(
        products,
        warehouses,
        demand=demand,
    )

    assert not warehouses.empty
    assert not suppliers.empty
    assert not inventory.empty

    assert {
        "snapshot_date",
        "warehouse_id",
        "product_id",
        "on_hand",
        "reserved",
    }.issubset(inventory.columns)

    assert (
        inventory["on_hand"] >= 0
    ).all()

    assert (
        inventory["reserved"] >= 0
    ).all()

    assert (
        inventory["reserved"]
        <= inventory["on_hand"]
    ).all()