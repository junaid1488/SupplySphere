import pandas as pd
import numpy as np

def sales_metrics(orders, items):
    x = items.merge(orders[["order_id","order_purchase_timestamp","customer_id","order_status"]], on="order_id", how="left")
    revenue = float(x["price"].sum())
    orders_n = int(x["order_id"].nunique())
    return {"revenue": revenue, "orders": orders_n, "average_order_value": revenue/orders_n if orders_n else 0.0}

def daily_sales(orders, items):
    x = items.merge(orders[["order_id","order_purchase_timestamp"]], on="order_id", how="left")
    x["date"] = pd.to_datetime(x["order_purchase_timestamp"], errors="coerce").dt.date
    return x.groupby("date", as_index=False).agg(revenue=("price","sum"), orders=("order_id","nunique"))

def customer_metrics(orders, items):
    x = items.merge(orders[["order_id","customer_id","order_purchase_timestamp"]], on="order_id", how="left")
    x["purchase_date"] = pd.to_datetime(x["order_purchase_timestamp"], errors="coerce")
    g = x.groupby("customer_id").agg(
        revenue=("price","sum"), orders=("order_id","nunique"),
        first_purchase=("purchase_date","min"), last_purchase=("purchase_date","max")
    ).reset_index()
    g["lifetime_days"] = (g["last_purchase"] - g["first_purchase"]).dt.days.fillna(0)
    g["repeat_customer"] = g["orders"] > 1
    return g

def seller_metrics(orders, items):
    x = items.merge(orders[["order_id","order_purchase_timestamp","order_delivered_customer_date",
                             "order_estimated_delivery_date"]], on="order_id", how="left")
    x["delivered"] = pd.to_datetime(x["order_delivered_customer_date"], errors="coerce")
    x["estimated"] = pd.to_datetime(x["order_estimated_delivery_date"], errors="coerce")
    x["late"] = x["delivered"] > x["estimated"]
    return x.groupby("seller_id").agg(
        revenue=("price","sum"), orders=("order_id","nunique"), late_rate=("late","mean")
    ).reset_index()

def delivery_metrics(orders, items):
    x = orders.copy()
    a = pd.to_datetime(x["order_purchase_timestamp"], errors="coerce")
    d = pd.to_datetime(x["order_delivered_customer_date"], errors="coerce")
    e = pd.to_datetime(x["order_estimated_delivery_date"], errors="coerce")
    x["delivery_days"] = (d-a).dt.total_seconds()/86400
    x["late"] = d > e
    x["freight_value"] = items.groupby("order_id")["freight_value"].sum().reindex(x["order_id"]).fillna(0).to_numpy()
    return x[["order_id","delivery_days","late","freight_value"]]

def daily_product_demand(orders, items):
    x = items.merge(orders[["order_id","order_purchase_timestamp"]], on="order_id", how="left")
    x["date"] = pd.to_datetime(x["order_purchase_timestamp"], errors="coerce").dt.floor("D")
    return x.groupby(["date","product_id"], as_index=False).agg(demand=("order_item_id","count"))
