CREATE TABLE IF NOT EXISTS core.customers (
    customer_id TEXT PRIMARY KEY,
    customer_unique_id TEXT NOT NULL,
    customer_zip_code_prefix INTEGER,
    customer_city TEXT,
    customer_state TEXT
);
CREATE TABLE IF NOT EXISTS core.orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES core.customers(customer_id),
    order_status TEXT NOT NULL,
    order_purchase_timestamp TIMESTAMP,
    order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
);
CREATE TABLE IF NOT EXISTS core.sellers (
    seller_id TEXT PRIMARY KEY,
    seller_zip_code_prefix INTEGER,
    seller_city TEXT,
    seller_state TEXT
);
CREATE TABLE IF NOT EXISTS core.products (
    product_id TEXT PRIMARY KEY,
    product_category_name TEXT,
    product_name_lenght INTEGER,
    product_description_lenght INTEGER,
    product_photos_qty INTEGER,
    product_weight_g DOUBLE PRECISION,
    product_length_cm DOUBLE PRECISION,
    product_height_cm DOUBLE PRECISION,
    product_width_cm DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS core.order_items (
    order_id TEXT NOT NULL REFERENCES core.orders(order_id),
    order_item_id INTEGER NOT NULL,
    product_id TEXT REFERENCES core.products(product_id),
    seller_id TEXT REFERENCES core.sellers(seller_id),
    shipping_limit_date TIMESTAMP,
    price DOUBLE PRECISION,
    freight_value DOUBLE PRECISION,
    PRIMARY KEY(order_id, order_item_id)
);
CREATE TABLE IF NOT EXISTS core.payments (
    order_id TEXT NOT NULL REFERENCES core.orders(order_id),
    payment_sequential INTEGER NOT NULL,
    payment_type TEXT,
    payment_installments INTEGER,
    payment_value DOUBLE PRECISION,
    PRIMARY KEY(order_id, payment_sequential)
);
CREATE TABLE IF NOT EXISTS core.reviews (
    review_id TEXT NOT NULL,
    order_id TEXT NOT NULL REFERENCES core.orders(order_id),
    review_score INTEGER,
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TIMESTAMP,
    review_answer_timestamp TIMESTAMP,
    PRIMARY KEY(review_id, order_id)
);
CREATE TABLE IF NOT EXISTS core.geolocation (
    geolocation_zip_code_prefix INTEGER NOT NULL,
    geolocation_lat DOUBLE PRECISION,
    geolocation_lng DOUBLE PRECISION,
    geolocation_city TEXT,
    geolocation_state TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON core.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_items_product ON core.order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_items_seller ON core.order_items(seller_id);
CREATE INDEX IF NOT EXISTS idx_orders_purchase_date ON core.orders(order_purchase_timestamp);
