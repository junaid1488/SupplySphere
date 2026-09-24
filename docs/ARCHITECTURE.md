# SupplySphere Architecture — Phases 0–5

Olist CSV → Raw/Staging → PostgreSQL Core → Analytics → Synthetic Operational Layer → Demand ML.

The database boundary is PostgreSQL. Analytics is generated from core relational entities. The synthetic
layer adds warehouses, inventory snapshots, suppliers, supplier products, purchase orders, transfers and
shipment events, including the 12-city Indian network. Demand forecasting uses temporal features and
baseline/model comparison with MAE, RMSE, WAPE and sMAPE.
