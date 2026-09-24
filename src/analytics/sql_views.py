ANALYTIC_VIEWS_SQL = {
"daily_product_demand": '''
CREATE OR REPLACE VIEW analytics.daily_product_demand AS
SELECT date_trunc('day', o.order_purchase_timestamp) AS demand_date,
       oi.product_id, COUNT(*)::BIGINT AS demand_units,
       SUM(oi.price)::DOUBLE PRECISION AS revenue
FROM core.order_items oi JOIN core.orders o ON o.order_id=oi.order_id
GROUP BY 1,2;
''',
"customer_metrics": '''
CREATE OR REPLACE VIEW analytics.customer_metrics AS
SELECT o.customer_id, COUNT(DISTINCT o.order_id)::BIGINT AS orders,
       SUM(oi.price)::DOUBLE PRECISION AS revenue,
       MIN(o.order_purchase_timestamp) AS first_purchase,
       MAX(o.order_purchase_timestamp) AS last_purchase
FROM core.orders o JOIN core.order_items oi ON oi.order_id=o.order_id
GROUP BY o.customer_id;
''',
"seller_metrics": '''
CREATE OR REPLACE VIEW analytics.seller_metrics AS
SELECT oi.seller_id, COUNT(DISTINCT oi.order_id)::BIGINT AS orders,
       SUM(oi.price)::DOUBLE PRECISION AS revenue
FROM core.order_items oi GROUP BY oi.seller_id;
''',
"delivery_metrics": '''
CREATE OR REPLACE VIEW analytics.delivery_metrics AS
SELECT order_id,
       EXTRACT(EPOCH FROM (order_delivered_customer_date-order_purchase_timestamp))/86400.0 AS delivery_days,
       CASE WHEN order_delivered_customer_date > order_estimated_delivery_date THEN TRUE ELSE FALSE END AS late
FROM core.orders;
''',
"inventory_metrics": '''
CREATE OR REPLACE VIEW analytics.inventory_metrics AS
SELECT product_id, COUNT(*)::BIGINT AS historical_demand_units,
       COUNT(DISTINCT order_id)::BIGINT AS orders
FROM core.order_items GROUP BY product_id;
'''
}
