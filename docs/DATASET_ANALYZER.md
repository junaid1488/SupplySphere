# Dataset Analyzer — Schema-Aware Dataset Analysis

Generic, schema-aware dataset analysis system. Upload any CSV or XLSX file and receive deterministic profiling, analytics, insights, and reports.

**Dataset Analyzer is NOT Olist.** It does not assume Olist data, Brazilian geography, or fixed product/supplier/warehouse names. Capabilities are determined entirely from the uploaded dataset's schema.

## Architecture

```
User uploads CSV/XLSX
        ↓
Secure temporary storage (filesystem)
        ↓
Dataset Reader (CSV/XLSX format handling)
        ↓
Deterministic Profiler (column types, statistics)
        ↓
Schema Intelligence (semantic role detection)
        ↓
Capability Detection (what analyses are possible)
        ↓
Analytics Engines (compute results from data)
        ├── KPI Engine
        ├── Analytics Engine
        ├── Trend Engine
        ├── Domain Engine
        ├── Geospatial Engine
        ├── Route Engine
        ├── Anomaly Engine
        ├── Query Engine (Ask Your Dataset)
        ├── Insights Engine
        └── Report Engine
        ↓
API responses → Frontend display
```

## Features

### Secure Upload

- Maximum file size: 500 MB
- Supported formats: CSV, XLSX (XLS not supported — xlwt deprecated)
- Extension validation, content/magic-byte validation
- Path traversal protection, safe filenames
- Streaming upload (no full RAM load)

### Dataset Profiling

Deterministic profiling computes from actual data:
- Row count, column count
- Column types (numeric, categorical, datetime, boolean)
- Null counts and percentages
- Unique value counts
- Numeric statistics (min, max, mean, median, std, sum, quartiles)
- Categorical summaries (value counts)
- Datetime ranges
- Duplicate row detection
- ID key candidates, measure candidates, geographic candidates

### Schema Intelligence

Semantic role detection via column name keyword matching and type inference:
- ID/Key, Entity, Product, Customer, Supplier
- Quantity, Price/Revenue/Value, Date/Time, Category, Status
- Inventory/Stock, Origin, Destination, Latitude, Longitude
- Loss/Damage, Expiry, Delivery/Shipment

Each detection includes confidence score, evidence, and uncertainty note.

### Capability Detection

Capabilities are determined from detected semantic roles:
- **Trend Analysis** — requires date/time + measure columns
- **Inventory Analysis** — requires inventory/stock column
- **Expiry Analysis** — requires expiry date column
- **Geospatial Analysis** — requires latitude + longitude columns
- **Route Analysis** — requires origin + destination columns
- **Supplier Analysis** — requires supplier column
- **Loss Analysis** — requires loss/damage column
- **Statistical Analysis** — requires numeric fields
- **Categorical Analysis** — requires categorical fields

A capability appears AVAILABLE only when its required fields are detected in the uploaded schema.

### Dynamic KPI Engine

Computes KPIs from actual data:
- Dataset overview (row count, column count, missing rate, duplicate rate)
- Numeric column statistics (sum, mean, median, min, max per column)
- Schema-aware KPIs based on detected roles (sales totals, inventory totals, zero-stock rates, date ranges, geographic coordinate validity, unique origins/destinations, route counts, category counts)

### Generic Analytics

- Numeric aggregations (count, mean, std, min, quartiles, max, sum)
- Category frequency analysis
- Group-by analysis (groupby + count + mean)
- Correlation analysis (Pearson correlation between numeric pairs)
- Top/bottom category values

### Trend Analysis

- Detects date + numeric column pairs
- Computes slope, R², p-value via linear regression
- Automatic period aggregation (daily for dense dates, monthly for sparse)
- Returns trend direction (increasing/decreasing/stable) and summary statistics

### Domain Analysis

Domain-specific analysis computed only when relevant fields exist:
- **Product/Sales** — entity performance, sales totals, unique entities
- **Inventory** — stock totals, averages, zero-stock analysis
- **Expiry** — expired/upcoming (30/90 days) counts from actual expiry fields
- **Supplier** — unique supplier counts where supplier fields exist
- **Loss/Damage** — loss counts and totals where loss fields exist
- **Generic** — entity/category/value analysis for any schema

### Geospatial Analysis

- Latitude/longitude column detection
- Valid/invalid coordinate counting
- Bounding box computation (min/max lat/lon)
- Coordinate distribution statistics

### Route Analysis

- Origin/destination column detection
- Unique origins, destinations, and routes
- Top routes by frequency
- Route frequency distribution
- Total route volume

### Anomaly Detection

Three statistical methods applied to numeric columns:
- **IQR** — Interquartile Range method (Q1 - 1.5*IQR, Q3 + 1.5*IQR)
- **Robust Z-Score** — median/MAD-based z-score
- **Standard Z-Score** — mean/std-based z-score (|z| > 3)

Reports affected rows, threshold, source columns, and limitations.

### Ask Your Dataset

Deterministic regex-based query engine. Supported patterns:

| Pattern | Example | Result |
|---------|---------|--------|
| Row count | "How many rows?" | Total row count |
| Column count | "How many columns?" | Total column count |
| Average | "What is the average sales?" | Mean of matching numeric column |
| Total/Sum | "What is the total revenue?" | Sum of matching numeric column |
| Minimum | "What is the lowest stock?" | Min of matching numeric column |
| Maximum | "What is the highest sales?" | Max of matching numeric column |
| Median | "What is the median price?" | Median of matching numeric column |
| Distinct count | "How many suppliers are there?" | Unique value count |
| Column info | "What is sales?" | Column profile information |
| Top entities | "Which category has the highest sales?" | Top categories by measure |
| Trend reference | "Show sales trend over time" | Reference to trend endpoint |

Unsupported questions return a controlled response with explanation. The system does NOT fabricate answers.

**Important:** Ask Your Dataset uses deterministic regex-based pattern matching. It is NOT a general-purpose natural-language reasoning engine.

### Evidence-Based Insights

All insights include:
- `source_columns` — which columns were used
- `calculation_basis` — how the insight was computed
- `limitations` — caveats and constraints

Insight types: stockout risk, supplier diversity, category concentration, data quality (duplicate rate), missingness, numeric variance.

No unsupported causal claims.

### Report Generation

Comprehensive report aggregating all analysis sections:
- Dataset summary (row count, column count, missing rate)
- All computed KPIs
- Insights summary
- Unavailable sections documented (not hidden)

## Security

Verified protections:
- 500 MB file size limit
- Extension validation (.csv, .xlsx only)
- Content/magic-byte validation (PK header for XLSX, CSV heuristic)
- Path traversal protection (dataset_id validation)
- Safe filenames (stored as `data.{ext}`)
- Isolated dataset directories
- Session-level access control
- API validation (400/404/410/413 error codes)
- Controlled error messages (no filesystem path leakage)
- Cleanup after failed uploads
- TTL-based expiration (default 1 hour)
- Cache invalidation on deletion

## Data Lifecycle

```
Upload → Temporary Storage → Session Created
    ↓
Profiling → Schema → Capabilities
    ↓
Analytics → KPIs → Trends → Domain → etc.
    ↓
Ask Your Dataset → Insights → Report
    ↓
Delete / TTL Expiry → Cleanup
```

Uploaded files are temporary filesystem data. They are NOT automatically imported into PostgreSQL/Prisma.

## Performance

Caching optimization:
- Profile computed once, cached per session
- Schema intelligence reuses cached profile
- Capability detection reuses cached profile + schema
- All compute endpoints share the profiling cache

Large dataset handling:
- Sampling for profiling (>100K rows)
- Chunked reading for data access
- Bounded result sizes

**Known limitation:** Individual compute engines may create their own DatasetReader and independently read the uploaded file. The system does NOT guarantee single-pass reading.

## API Reference

Base path: `/api/dataset-analyzer`

All endpoints accept/return JSON. Session IDs are `ds_` prefixed strings.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions` | Upload dataset (multipart/form-data) |
| GET | `/sessions` | List all sessions |
| GET | `/sessions/{id}` | Get session metadata |
| DELETE | `/sessions/{id}` | Delete dataset and session |
| GET | `/sessions/{id}/preview` | Preview first N rows |
| GET | `/sessions/{id}/sample` | Random sample of rows |
| GET | `/sessions/{id}/sheets` | List XLSX sheet names |
| GET | `/sessions/{id}/sheets/{name}` | Read specific sheet |
| GET | `/sessions/{id}/columns` | Column information |
| GET | `/sessions/{id}/row-count` | Row count |
| POST | `/sessions/{id}/read-chunked` | Chunked CSV reading |
| GET | `/sessions/{id}/profile` | Full dataset profile |
| GET | `/sessions/{id}/schema` | Schema intelligence |
| GET | `/sessions/{id}/capabilities` | Detected capabilities |
| GET | `/sessions/{id}/kpis` | Key performance indicators |
| GET | `/sessions/{id}/analytics` | Analytics results |
| GET | `/sessions/{id}/trends` | Trend analysis |
| GET | `/sessions/{id}/domain` | Domain analysis |
| GET | `/sessions/{id}/geospatial` | Geospatial analysis |
| GET | `/sessions/{id}/routes` | Route analysis |
| GET | `/sessions/{id}/anomalies` | Anomaly detection |
| POST | `/sessions/{id}/ask` | Ask Your Dataset (body: `{"question": "..."}`) |
| GET | `/sessions/{id}/insights` | Evidence-based insights |
| GET | `/sessions/{id}/report` | Comprehensive report |
| POST | `/cleanup` | Cleanup expired sessions |

## Testing

Verified by STEP 21 regression (220/220 runnable tests pass):
- `test_dataset_analyzer.py` — Models, storage, sessions, readers, security (66 passed, 2 skipped)
- `test_cache_behavior.py` — Profiling cache optimization (6 passed)
- `test_step9_15.py` — Domain, geospatial, routes, anomalies, queries, insights, report (62 passed)
- `test_kpi_analytics_trend.py` — KPI, analytics, trend engines (24 passed)
- `test_step19_api_integration.py` — API routes and contracts (24 passed)

## Known Limitations

1. XLS format not supported (xlwt deprecated). Use XLSX.
2. Ask Your Dataset is regex-based pattern matching, not NL inference.
3. Individual engines may independently read uploaded files.
4. Deprecation warnings for `datetime.utcnow()` and `numpy.timedelta` (cosmetic).
