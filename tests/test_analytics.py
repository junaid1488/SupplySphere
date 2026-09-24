import pandas as pd
from src.analytics.metrics import sales_metrics,customer_metrics,daily_product_demand

def fixtures():
    orders=pd.DataFrame({"order_id":["o1","o2"],"customer_id":["c1","c1"],
        "order_purchase_timestamp":["2024-01-01","2024-01-02"],"order_status":["delivered","delivered"]})
    items=pd.DataFrame({"order_id":["o1","o2"],"order_item_id":[1,1],"product_id":["p1","p1"],
        "seller_id":["s1","s1"],"price":[100.,200.],"freight_value":[10.,20.]})
    return orders,items

def test_sales():
    o,i=fixtures(); m=sales_metrics(o,i)
    assert m["revenue"]==300
    assert m["orders"]==2
    assert m["average_order_value"]==150

def test_customer_and_daily():
    o,i=fixtures()
    cm=customer_metrics(o,i)
    assert int(cm.loc[0,"orders"])==2
    dd=daily_product_demand(o,i)
    assert len(dd)==2
