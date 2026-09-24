import pandas as pd

# Load all raw datasets
orders = pd.read_csv(r"C:\Users\DELL\Downloads\SupplySphere\supply-sphere-phase11\supply-sphere\data\raw\olist_orders_dataset.csv")
order_items = pd.read_csv(r"C:\Users\DELL\Downloads\SupplySphere\supply-sphere-phase11\supply-sphere\data\raw\olist_order_items_dataset.csv")
sellers = pd.read_csv(r"C:\Users\DELL\Downloads\SupplySphere\supply-sphere-phase11\supply-sphere\data\raw\olist_sellers_dataset.csv")
customers = pd.read_csv(r"C:\Users\DELL\Downloads\SupplySphere\supply-sphere-phase11\supply-sphere\data\raw\olist_customers_dataset.csv")
geolocation = pd.read_csv(r"C:\Users\DELL\Downloads\SupplySphere\supply-sphere-phase11\supply-sphere\data\raw\olist_geolocation_dataset.csv")

print("=== ROW COUNTS ===")
print(f"Orders: {len(orders):,}")
print(f"Order Items: {len(order_items):,}")
print(f"Sellers: {len(sellers):,}")
print(f"Customers: {len(customers):,}")
print(f"Geolocation: {len(geolocation):,}")

print("\n=== COLUMNS ===")
print(f"Orders cols: {list(orders.columns)}")
print(f"Order Items cols: {list(order_items.columns)}")
print(f"Sellers cols: {list(sellers.columns)}")
print(f"Customers cols: {list(customers.columns)}")
print(f"Geolocation cols: {list(geolocation.columns)}")

print("\n=== BASIC STATS ===")
print(f"Unique orders in order_items: {order_items['order_id'].nunique():,}")
print(f"Unique sellers in order_items: {order_items['seller_id'].nunique():,}")
print(f"Unique customers in orders: {orders['customer_id'].nunique():,}")
print(f"Unique seller ZIPs: {sellers['seller_zip_code_prefix'].nunique():,}")
print(f"Unique customer ZIPs: {customers['customer_zip_code_prefix'].nunique():,}")
print(f"Unique geolocation ZIPs: {geolocation['geolocation_zip_code_prefix'].nunique():,}")

# Join chains
print("\n=== JOIN: Order -> Customer ===")
orders_customers = orders.merge(customers, on='customer_id', how='left')
print(f"Orders with customer match: {orders_customers['customer_zip_code_prefix'].notna().sum():,} / {len(orders):,}")

print("\n=== JOIN: Order -> Order_Items -> Seller ===")
orders_items = orders.merge(order_items, on='order_id', how='left')
print(f"Orders with items: {orders_items['order_item_id'].notna().sum():,} / {len(orders):,}")
orders_items_sellers = orders_items.merge(sellers, on='seller_id', how='left')
print(f"Order-items with seller match: {orders_items_sellers['seller_zip_code_prefix'].notna().sum():,} / {len(orders_items):,}")

# Deduplicate geolocation first (mean lat/lng per ZIP) - as done in geospatial service
geo_dedup = geolocation.groupby('geolocation_zip_code_prefix', as_index=False).agg({
    'geolocation_lat': 'mean',
    'geolocation_lng': 'mean',
    'geolocation_city': 'first',
    'geolocation_state': 'first'
})
print(f"\nDeduped geolocation ZIPs: {len(geo_dedup):,}")

# Geolocation resolution
print("\n=== GEOLOCATION COVERAGE ===")
# Seller ZIP -> Geolocation
seller_geo = sellers.merge(
    geo_dedup.rename(columns={'geolocation_zip_code_prefix': 'seller_zip_code_prefix',
                                 'geolocation_lat': 'seller_lat',
                                 'geolocation_lng': 'seller_lng',
                                 'geolocation_city': 'seller_geo_city',
                                 'geolocation_state': 'seller_geo_state'}),
    on='seller_zip_code_prefix', how='left'
)
print(f"Sellers with coordinates: {seller_geo['seller_lat'].notna().sum():,} / {len(sellers):,}")
print(f"Sellers with valid coords (lat/lng not null): {seller_geo.dropna(subset=['seller_lat', 'seller_lng']).shape[0]:,}")

# Customer ZIP -> Geolocation
customer_geo = customers.merge(
    geo_dedup.rename(columns={'geolocation_zip_code_prefix': 'customer_zip_code_prefix',
                                 'geolocation_lat': 'customer_lat',
                                 'geolocation_lng': 'customer_lng',
                                 'geolocation_city': 'customer_geo_city',
                                 'geolocation_state': 'customer_geo_state'}),
    on='customer_zip_code_prefix', how='left'
)
print(f"Customers with coordinates: {customer_geo['customer_lat'].notna().sum():,} / {len(customers):,}")
print(f"Customers with valid coords: {customer_geo.dropna(subset=['customer_lat', 'customer_lng']).shape[0]:,}")

# Full chain: Order -> Customer + Seller with coordinates
print("\n=== FULL CHAIN: Order with BOTH seller and customer coordinates ===")
# Start with order-items that have sellers
oi_seller = order_items.merge(sellers, on='seller_id', how='left')
oi_seller_geo = oi_seller.merge(
    geo_dedup.rename(columns={'geolocation_zip_code_prefix': 'seller_zip_code_prefix',
                                 'geolocation_lat': 'seller_lat',
                                 'geolocation_lng': 'seller_lng'}),
    on='seller_zip_code_prefix', how='left'
)

# Customer side
order_cust = orders.merge(customers, on='customer_id', how='left')
order_cust_geo = order_cust.merge(
    geo_dedup.rename(columns={'geolocation_zip_code_prefix': 'customer_zip_code_prefix',
                                 'geolocation_lat': 'customer_lat',
                                 'geolocation_lng': 'customer_lng'}),
    on='customer_zip_code_prefix', how='left'
)

# Combine: order_items with seller coords + orders with customer coords
full = oi_seller_geo.merge(
    order_cust_geo[['order_id', 'customer_lat', 'customer_lng', 'customer_zip_code_prefix']],
    on='order_id', how='left'
)

print(f"Total order-item rows: {len(full):,}")
print(f"Rows with seller coords: {full['seller_lat'].notna().sum():,}")
print(f"Rows with customer coords: {full['customer_lat'].notna().sum():,}")
print(f"Rows with BOTH coords: {full.dropna(subset=['seller_lat', 'seller_lng', 'customer_lat', 'customer_lng']).shape[0]:,}")

# Unique locations
seller_locs = seller_geo.dropna(subset=['seller_lat', 'seller_lng'])
customer_locs = customer_geo.dropna(subset=['customer_lat', 'customer_lng'])
print(f"\nUnique seller locations (by ZIP): {seller_locs['seller_zip_code_prefix'].nunique():,}")
print(f"Unique customer locations (by ZIP): {customer_locs['customer_zip_code_prefix'].nunique():,}")

# Unique seller->customer pairs at ZIP level
both = full.dropna(subset=['seller_lat', 'seller_lng', 'customer_lat', 'customer_lng'])
pairs = both[['seller_zip_code_prefix', 'customer_zip_code_prefix']].drop_duplicates()
print(f"Unique seller_ZIP -> customer_ZIP pairs: {len(pairs):,}")

# Check data quality
print("\n=== DATA QUALITY ===")
print(f"Orders missing customer_id: {orders['customer_id'].isna().sum():,}")
print(f"Order items missing seller_id: {order_items['seller_id'].isna().sum():,}")
print(f"Sellers missing ZIP: {sellers['seller_zip_code_prefix'].isna().sum():,}")
print(f"Customers missing ZIP: {customers['customer_zip_code_prefix'].isna().sum():,}")

# Geolocation duplicates (before dedup)
geo_dupes = geolocation.groupby('geolocation_zip_code_prefix').size().reset_index(name='count')
print(f"Geolocation ZIPs with multiple rows: {(geo_dupes['count'] > 1).sum():,}")
print(f"Max rows per ZIP: {geo_dupes['count'].max():,}")

# Coordinate ranges
print(f"\nGeolocation lat range: {geolocation['geolocation_lat'].min():.4f} to {geolocation['geolocation_lat'].max():.4f}")
print(f"Geolocation lng range: {geolocation['geolocation_lng'].min():.4f} to {geolocation['geolocation_lng'].max():.4f}")

# Check for non-Brazil coordinates (Brazil approx: lat -33 to 5, lng -74 to -30)
non_brazil = geolocation[
    (geolocation['geolocation_lat'] > 5) | 
    (geolocation['geolocation_lat'] < -34) | 
    (geolocation['geolocation_lng'] > -30) | 
    (geolocation['geolocation_lng'] < -75)
]
print(f"Potential non-Brazil coordinates: {len(non_brazil):,}")

# Invalid coordinates (0,0 or null)
invalid = geolocation[
    (geolocation['geolocation_lat'] == 0) & (geolocation['geolocation_lng'] == 0)
]
print(f"Zero coordinates: {len(invalid):,}")

# Row multiplication check
print("\n=== ROW MULTIPLICATION CHECK ===")
# One order can have multiple items (multiple sellers)
items_per_order = order_items.groupby('order_id').size()
print(f"Items per order - min: {items_per_order.min()}, max: {items_per_order.max()}, mean: {items_per_order.mean():.2f}")
print(f"Orders with >1 item: {(items_per_order > 1).sum():,} ({(items_per_order > 1).mean()*100:.1f}%)")

# One seller can have multiple ZIPs? No, seller has one ZIP
print(f"Sellers with duplicate seller_id: {sellers['seller_id'].duplicated().sum():,}")
print(f"Customers with duplicate customer_id: {customers['customer_id'].duplicated().sum():,}")

# Geolocation ZIP duplicates - how many unique lat/lng per ZIP
geo_unique = geolocation.groupby('geolocation_zip_code_prefix').agg({
    'geolocation_lat': 'nunique',
    'geolocation_lng': 'nunique'
}).reset_index()
multi_coord = geo_unique[(geo_unique['geolocation_lat'] > 1) | (geo_unique['geolocation_lng'] > 1)]
print(f"ZIPs with multiple distinct coordinates: {len(multi_coord):,}")

EOF