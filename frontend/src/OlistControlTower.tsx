import React from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster'
import 'leaflet.heat'

type Item = Record<string, unknown>

type Page = {
  items: Item[]
  total: number
}

type OptimizationResult = {
  solver?: string
  status?: string
  current_cost?: number
  optimized_cost?: number
  estimated_savings?: number
  service_level?: number
  stockout_risk?: number
  supplier_rows?: number
  warehouse_rows?: number
  transfer_rows?: number
  supplier_count?: number
  warehouse_count?: number
  demand_rows?: number
  inventory_rows?: number
  demand_snapshot_date?: string
  time_limit_ms?: number
}

type Insight = {
  category: string
  severity: 'critical' | 'high' | 'warning' | 'info'
  title: string
  description: string
  action: string
  count: number
}

type InsightsResponse = {
  items: Insight[]
  total: number
  generated_at: string
}

type ReportData = {
  summary?: {
    revenue?: number
    orders?: number
  }
  inventory_risk?: {
    total_at_risk: number
    high: number
    critical: number
  }
  delivery_risk?: {
    total_at_risk: number
    high: number
    critical: number
  }
  supplier_risk?: {
    total_at_risk: number
    high: number
    critical: number
  }
  operational_metrics?: {
    latest_snapshot_date?: string
    total_on_hand?: number
    zero_stock_skus?: number
    unique_products?: number
    unique_warehouses?: number
  }
  forecast_performance?: {
    selected_model?: string
    wape?: number
    smape?: number
    mae?: number
    rmse?: number
    accuracy?: number
    records?: number
    products_forecasted?: number
  }
  optimization_result?: {
    solver?: string
    status?: string
    current_cost?: number
    optimized_cost?: number
    estimated_savings?: number
    service_level?: number
    stockout_risk?: number
    transfers_recommended?: number
  }
  generated_at: string
}

type ReportResponse = ReportData

type ApiResponse = Page | OptimizationResult | InsightsResponse | ReportResponse | Item

function isOptimizationResult(data: ApiResponse): data is OptimizationResult {
  return !Array.isArray(data) && 'solver' in data
}

function isInsightsResponse(data: ApiResponse): data is InsightsResponse {
  return !Array.isArray(data) && 'items' in data && 'generated_at' in data && Array.isArray(data.items) && data.items.length > 0 && 'severity' in data.items[0]
}

function isReportResponse(data: ApiResponse): data is ReportResponse {
  return !Array.isArray(data) && 'generated_at' in data && ('summary' in data || 'inventory_risk' in data || 'optimization_result' in data)
}

function isPage(data: ApiResponse): data is Page {
  return !Array.isArray(data) && 'items' in data && 'total' in data && Array.isArray(data.items)
}

type DashboardSummary = {
  revenue?: number | null
  orders?: number | null
  inventory_value?: number | null
  stockout_risks?: number
  stockout_high?: number
  stockout_critical?: number
  delayed_shipments?: number
  delayed_shipments_high?: number
  delayed_shipments_critical?: number
  forecast_accuracy?: number | null
  forecast_wape?: number | null
  forecast_smape?: number | null
  forecast_mae?: number | null
  forecast_rmse?: number | null
  forecast_model?: string | null
  supplier_risks?: number
  supplier_risks_high?: number
  supplier_risks_critical?: number
  optimization_savings?: number | null
}

function isDashboardSummary(data: unknown): data is DashboardSummary {
  return typeof data === 'object' && data !== null && !Array.isArray(data)
}

/* ── formatting helpers ── */
function fmtMoney(value: unknown) {
  const n = Number(value)
  return Number.isFinite(n)
    ? '$' + n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })
    : '—'
}

function fmtNum(value: unknown) {
  const n = Number(value)
  return Number.isFinite(n) ? n.toLocaleString() : '—'
}

function fmtPct(value: unknown, digits = 1) {
  const n = Number(value)
  return Number.isFinite(n) ? (n * 100).toFixed(digits) + '%' : '—'
}

function riskClass(value: unknown) {
  const level = String(value ?? '').toLowerCase()
  if (level === 'critical') return 'critical'
  if (level === 'high') return 'high'
  if (level === 'medium' || level === 'medium risk') return 'medium'
  if (level === 'low') return 'low'
  return ''
}

/* ── risk-level badge ── */
function RiskBadge({ value }: { value: unknown }) {
  const cls = riskClass(value)
  return <span className={`ct-risk-badge ${cls}`}>{(value as string) ?? '—'}</span>
}

/* ── generic data table config ── */
type Column = {
  key: string
  label: string
  format?: (value: unknown) => string
  render?: (value: unknown, row: Item) => React.ReactNode
}

/* reusable operational data table with search / risk filter / pagination */
function OperativeTable({
  title,
  subtitle,
  endpoint,
  columns,
  searchKeys,
  searchPlaceholder,
  riskable,
}: {
  title: string
  subtitle?: string
  endpoint: string
  columns: Column[]
  searchKeys: string[]
  searchPlaceholder: string
  riskable?: { key: string; levels: string[] }
}) {
  const [dataItems, setDataItems] = React.useState<Item[]>([])
  const [total, setTotal] = React.useState(0)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')
  const [search, setSearch] = React.useState('')
  const [risk, setRisk] = React.useState('all')
  const [page, setPage] = React.useState(0)
  const pageSize = 10

  React.useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    api(endpoint, controller.signal)
      .then((data) => {
        if (isPage(data)) {
          setDataItems(data.items)
          setTotal(data.total)
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [endpoint])

  const filtered = React.useMemo(() => {
    const q = search.trim().toLowerCase()
    return dataItems.filter((item) => {
      if (risk !== 'all' && String(item[riskable?.key ?? ''] ?? '').toLowerCase() !== risk) return false
      if (!q) return true
      return searchKeys.some((k) => String(item[k] ?? '').toLowerCase().includes(q))
    })
  }, [dataItems, search, risk, riskable, searchKeys])

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const rows = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize)

  React.useEffect(() => { setPage(0) }, [search, risk])

  return (
    <section className="panel">
      <div className="table-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <span className="insights-meta">{fmtNum(total)} records · {dataItems.length} loaded</span>
      </div>

      <div className="ct-toolbar">
        <input
          placeholder={searchPlaceholder}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {riskable && (
          <select value={risk} onChange={(e) => setRisk(e.target.value)}>
            <option value="all">All risk levels</option>
            {riskable.levels.map((l) => <option key={l} value={l.toLowerCase()}>{l}</option>)}
          </select>
        )}
      </div>

      {loading && <div className="region-loading">Loading {title.toLowerCase()}…</div>}
      {error && <div className="error">{error}</div>}
      {!loading && !error && filtered.length === 0 && (
        <div className="insights-empty">No records match the current filters.</div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>{columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={index}>
                    {columns.map((c) => (
                      <td key={c.key}>
                        {c.render
                          ? c.render(row[c.key], row)
                          : c.format
                            ? c.format(row[c.key])
                            : popupValue(row[c.key])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="ct-pagination">
            <button disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>Prev</button>
            <span>Page {safePage + 1} of {pageCount} · {fmtNum(filtered.length)} filtered</span>
            <button disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}>Next</button>
          </div>
        </>
      )}
    </section>
  )
}

/* ── Dashboard KPIs from /api/dashboard/summary ── */
function DashboardView({ onOpenTab }: { onOpenTab: (tab: string) => void }) {
  const [summary, setSummary] = React.useState<DashboardSummary | null>(null)
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    const controller = new AbortController()
    api('/api/dashboard/summary', controller.signal)
      .then((data) => setSummary(isDashboardSummary(data) ? data : null))
      .catch((e) => { if (!controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [])

  const kpis: Array<{ label: string; value: string; sub?: string; tone?: string; tab?: string }> = [
    { label: 'Revenue', value: fmtMoney(summary?.revenue), sub: 'Total sales', tab: 'Reports' },
    { label: 'Orders', value: fmtNum(summary?.orders), sub: 'Processed orders', tab: 'Reports' },
    { label: 'Inventory Value', value: fmtMoney(summary?.inventory_value), sub: 'On-hand valuation', tab: 'Inventory' },
    { label: 'Forecast Accuracy', value: summary?.forecast_accuracy != null ? fmtPct(summary.forecast_accuracy) : '—', sub: summary?.forecast_model ? `Model: ${summary.forecast_model}` : 'No model artifact', tab: 'Demand Forecast' },
  ]

  const riskCards: Array<{ label: string; value: number; high: number | undefined; critical: number | undefined; tab: string }> = [
    { label: 'Stockout risks', value: summary?.stockout_risks ?? 0, high: summary?.stockout_high, critical: summary?.stockout_critical, tab: 'Inventory' },
    { label: 'Delayed shipments', value: summary?.delayed_shipments ?? 0, high: summary?.delayed_shipments_high, critical: summary?.delayed_shipments_critical, tab: 'Logistics' },
    { label: 'Supplier risks', value: summary?.supplier_risks ?? 0, high: summary?.supplier_risks_high, critical: summary?.supplier_risks_critical, tab: 'Suppliers' },
  ]

  const forecastMetrics: Array<{ label: string; value: string }> = [
    { label: 'WAPE', value: summary?.forecast_wape != null ? Number(summary.forecast_wape).toFixed(3) : '—' },
    { label: 'sMAPE', value: summary?.forecast_smape != null ? Number(summary.forecast_smape).toFixed(3) : '—' },
    { label: 'MAE', value: summary?.forecast_mae != null ? Number(summary.forecast_mae).toFixed(2) : '—' },
    { label: 'RMSE', value: summary?.forecast_rmse != null ? Number(summary.forecast_rmse).toFixed(2) : '—' },
  ]

  return (
    <>
      {error && <div className="error">{error}</div>}

      <section className="panel">
        <div className="table-head">
          <div>
            <h2>Executive Overview</h2>
            <p>Live performance indicators computed from the operational network.</p>
          </div>
          {summary?.optimization_savings != null && (
            <div className="opt-card" style={{ minWidth: 200 }}>
              <h3>Optimization Savings</h3>
              <div className="opt-value savings">{fmtMoney(summary.optimization_savings)}</div>
            </div>
          )}
        </div>

        <div className="ct-summary-grid">
          {kpis.map((k) => (
            <article key={k.label} className="ct-summary-card" onClick={() => k.tab && onOpenTab(k.tab)} style={k.tab ? { cursor: 'pointer' } : undefined}>
              <span className="ct-summary-label">{k.label}</span>
              <span className="ct-summary-value">{k.value}</span>
              {k.sub && <span className="ct-summary-sub">{k.sub}</span>}
            </article>
          ))}
        </div>

        <div className="ct-summary-grid">
          {riskCards.map((c) => (
            <article key={c.label} className="ct-summary-card" onClick={() => onOpenTab(c.tab)} style={{ cursor: 'pointer' }}>
              <span className="ct-summary-label">{c.label}</span>
              <span className="ct-summary-value">{fmtNum(c.value)}</span>
              <span className="ct-summary-sub">
                High: {fmtNum(c.high)} · Critical: {fmtNum(c.critical)}
              </span>
            </article>
          ))}
          {forecastMetrics.length > 0 && (
            <article className="ct-summary-card">
              <span className="ct-summary-label">Error Metrics</span>
              <span className="ct-summary-sub" style={{ marginTop: 8 }}>
                {forecastMetrics.map((m) => (
                  <div key={m.label} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '2px 0' }}>
                    <span>{m.label}</span>
                    <strong style={{ color: 'var(--ss-text)' }}>{m.value}</strong>
                  </div>
                ))}
              </span>
            </article>
          )}
        </div>
      </section>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="table-head">
            <h2>Supply Network</h2>
          </div>
          <MapView />
        </section>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <section className="panel">
            <div className="table-head">
              <h2>Operational Modules</h2>
            </div>
            <div className="ct-summary-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))' }}>
              {['Demand Forecast', 'Inventory', 'Warehouses', 'Suppliers', 'Logistics', 'Geospatial', 'Optimization', 'AI Insights', 'Reports'].map((t) => (
                <article key={t} className="ct-summary-card" onClick={() => onOpenTab(t)} style={{ cursor: 'pointer' }}>
                  <span className="ct-summary-label">Module</span>
                  <span className="ct-summary-value" style={{ fontSize: 14 }}>{t}</span>
                </article>
              ))}
            </div>
          </section>
        </div>
      </div>
    </>
  )
}

type LayerName =
  | 'warehouses'
  | 'customers'
  | 'sellers'
  | 'orders'
  | 'demand'
  | 'inventory'
  | 'delivery'
  | 'transfers'
  | 'routes'
  | 'shipping_lanes'

type LayerState = Record<LayerName, boolean>

type NetworkName = 'brazil' | 'india'

function layerLabel(name: LayerName, network: NetworkName = 'brazil'): string {
  if (name === 'shipping_lanes') return 'Shipping Lanes'
  if (name === 'warehouses') return network === 'india' ? 'Warehouses · India' : 'Warehouses · Synthetic Demo'
  return name
}

const NETWORK_SCOPED_LAYERS: LayerName[] = ['warehouses', 'transfers', 'routes']

type Filters = {
  state: string
  city: string
}

type Coordinate = {
  latitude: number
  longitude: number
}

type HeatLayer = L.Layer & {
  setLatLngs?: (
    latlngs: Array<[number, number, number]>,
  ) => HeatLayer
}

const api = async (path: string, signal?: AbortSignal) => {
  const response = await fetch(path, { signal })

  if (!response.ok) {
    throw new Error(
      `${response.status} ${response.statusText}`,
    )
  }

  return response.json()
}

const warehouseIcon = L.divIcon({
  className: 'warehouse-marker',
  html: '<span>W</span>',
  iconSize: [30, 30],
  iconAnchor: [15, 15],
})

const sellerIcon = L.divIcon({
  className: 'seller-marker',
  html: '<span>S</span>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
})

const BRAZIL_BOUNDS = L.latLngBounds(
  [-33.75, -73.99],
  [5.27, -34.79],
)

const INDIA_BOUNDS = L.latLngBounds(
  [12.9716, 72.5714],
  [28.6139, 91.7362],
)

const brazilViewOptions: L.FitBoundsOptions = {
  padding: [40, 40],
  maxZoom: 6,
}

function popupValue(value: unknown) {
  return String(value ?? '')
}

function coordinate(
  item: Item,
): Coordinate | null {
  const latitude = Number(item.latitude)
  const longitude = Number(item.longitude)

  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude)
  ) {
    return null
  }

  return {
    latitude,
    longitude,
  }
}

function MapView() {
  const mapRef =
    React.useRef<HTMLDivElement>(null)

  const mapInstance =
    React.useRef<L.Map | null>(null)

  const layerRefs =
    React.useRef<Record<string, L.Layer>>({})

  const cache =
    React.useRef<Record<string, Item[]>>({})

  const layerAbortRef =
    React.useRef<AbortController | null>(null)

  const loadingCountRef =
    React.useRef(0)

  const shippingLaneFitRef =
    React.useRef(false)

  const [layers, setLayers] =
    React.useState<LayerState>({
      warehouses: true,
      customers: false,
      sellers: false,
      orders: false,
      demand: false,
      inventory: false,
      delivery: false,
      transfers: true,
      routes: false,
      shipping_lanes: false,
    })

  const [filters, setFilters] =
    React.useState<Filters>({
      state: '',
      city: '',
    })

  const [network, setNetwork] =
    React.useState<NetworkName>('brazil')

  const [filterOptions, setFilterOptions] =
    React.useState({
      states: [] as string[],
      cities: [] as string[],
    })

  const [loading, setLoading] =
    React.useState(false)

  const [mapError, setMapError] =
    React.useState('')

  const clearLayer = (
    name: string,
  ) => {
    const existing =
      layerRefs.current[name]

    if (
      existing &&
      'clearLayers' in existing
    ) {
      ;(
        existing as L.LayerGroup
      ).clearLayers()
    }

    if (
      existing &&
      mapInstance.current?.hasLayer(
        existing,
      )
    ) {
      mapInstance.current.removeLayer(
        existing,
      )
    }

    delete layerRefs.current[name]
  }

  const filtered = (
    items: Item[],
  ) => {
    return items.filter((item) => {
      const state =
        filters.state.toLowerCase()

      const city =
        filters.city.toLowerCase()

      const itemState =
        String(
          item.state ??
            item.customer_state ??
            '',
        ).toLowerCase()

      const itemCity =
        String(
          item.city ??
            item.customer_city ??
            '',
        ).toLowerCase()

      if (
        state &&
        itemState !== state
      ) {
        return false
      }

      if (
        city &&
        itemCity !== city
      ) {
        return false
      }

      return true
    })
  }
  const updateFilterOptions = (
    items: Item[],
  ) => {
    const newStates = Array.from(
      new Set(
        items
          .map((item) =>
            String(
              item.state ??
                item.customer_state ??
                '',
            ).trim(),
          )
          .filter(Boolean),
      ),
    )

    const newCities = Array.from(
      new Set(
        items
          .map((item) =>
            String(
              item.city ??
                item.customer_city ??
                '',
            ).trim(),
          )
          .filter(Boolean),
      ),
    )

    setFilterOptions(
      (current) => ({
        states: Array.from(
          new Set([
            ...current.states,
            ...newStates,
          ]),
        ).sort(),
        cities: Array.from(
          new Set([
            ...current.cities,
            ...newCities,
          ]),
        ).sort(),
      }),
    )
  }
  const fetchLayerData = async (
    name: LayerName,
    signal?: AbortSignal,
  ) => {
    const scoped = NETWORK_SCOPED_LAYERS.includes(name)
    const cacheKey = scoped ? `${name}:${network}` : name

    if (cache.current[cacheKey]) {
      return cache.current[cacheKey]
    }

    const limits: Record<
      LayerName,
      number
    > = {
      warehouses: 500,
      customers: 10000,
      sellers: 5000,
      orders: 5000,
      demand: 5000,
      inventory: 5000,
      delivery: 5000,
      transfers: 5000,
      routes: 500,
      shipping_lanes: 2000,
    }

    const endpoint =
      name === 'shipping_lanes'
        ? 'shipping-lanes'
        : name

    const networkQuery = scoped
      ? `&network=${network}`
      : ''

    const response: Page =
      await api(
        `/api/geospatial/${endpoint}?limit=${limits[name]}${networkQuery}`,
        signal,
      )

    cache.current[cacheKey] =
      response.items

    return response.items
  }

  const addClusteredPoints = (
    items: Item[],
    icon: L.Icon | L.DivIcon,
    popup: (
      item: Item,
    ) => string,
  ) => {
    const cluster =
      L.markerClusterGroup({
        chunkedLoading: true,
        maxClusterRadius: 55,
      })

    filtered(items).forEach(
      (item) => {
        const location =
          coordinate(item)

        if (!location) {
          return
        }

        L.marker(
          [
            location.latitude,
            location.longitude,
          ],
          { icon },
        )
          .bindPopup(
            popup(item),
          )
          .addTo(cluster)
      },
    )

    return cluster
  }

  const addHeatmap = (
    items: Item[],
    value: (
      item: Item,
    ) => number,
  ) => {
    const points =
      filtered(items)
        .map((item) => {
          const location =
            coordinate(item)

          if (!location) {
            return null
          }

          const weight =
            Number(value(item))

          if (!Number.isFinite(weight)) {
            return null
          }

          return [
            location.latitude,
            location.longitude,
            Math.max(0, weight),
          ] as [
            number,
            number,
            number,
          ]
        })
        .filter(
          (
            item,
          ): item is [
            number,
            number,
            number,
          ] => item !== null,
        )

    const heatFactory = (
      L as typeof L & {
        heatLayer: (
          latlngs: Array<
            [number, number, number]
          >,
          options?: {
            radius?: number
            blur?: number
            maxZoom?: number
          },
        ) => HeatLayer
      }
    ).heatLayer

    return heatFactory(points, {
      radius: 28,
      blur: 22,
      maxZoom: 10,
    })
  }

  const loadLayer = async (
    name: LayerName,
    signal?: AbortSignal,
  ) => {
    const map =
      mapInstance.current

    if (!map) {
      return
    }

    clearLayer(name)

    if (!layers[name]) {
      return
    }

    loadingCountRef.current += 1
    setLoading(true)
    setMapError('')

    try {
      const items =
        await fetchLayerData(name, signal)

      if (
        signal?.aborted
      ) {
        return
      }

      if (
        name === 'customers' ||
        name === 'sellers' ||
        name === 'orders'
      ) {
        updateFilterOptions(items)
      }

      if (
        name === 'warehouses'
      ) {
        const group =
          L.layerGroup()

        filtered(items).forEach(
          (item) => {
            const location =
              coordinate(item)

            if (!location) {
              return
            }

            L.marker(
              [
                location.latitude,
                location.longitude,
              ],
              {
                icon:
                  warehouseIcon,
              },
            )
              .bindPopup(
                network === 'india'
                  ? `
                <strong>India Warehouse</strong>
                <br/>
                ${popupValue(item.warehouse_name ?? item.city)}
                <br/>
                ${popupValue(item.city)}${item.state ? `, ${popupValue(item.state)}` : ''}
                <br/>
                ID: ${popupValue(item.warehouse_id)}
                `
                  : `
                <strong>Synthetic Demo Warehouse</strong>
                <br/>
                ${popupValue(item.warehouse_name)}
                <br/>
                ${popupValue(item.city)}, ${popupValue(item.state)}
                <br/>
                ID: ${popupValue(item.warehouse_id)}
                `,
              )
              .addTo(group)
          },
        )

        layerRefs.current[name] =
          group

        group.addTo(map)
      }

      if (
        name === 'customers'
      ) {
        const group =
          addClusteredPoints(
            items,
            L.divIcon({
              className:
                'customer-marker',
              html:
                '<span>C</span>',
              iconSize: [
                12,
                12,
              ],
              iconAnchor: [
                6,
                6,
              ],
            }),
            (item) => `
              <strong>Customer</strong>
              <br/>
              ID: ${popupValue(item.customer_id)}
              <br/>
              ${popupValue(item.city)}, ${popupValue(item.state)}
            `,
          )

        layerRefs.current[name] =
          group

        group.addTo(map)
      }

      if (
        name === 'sellers'
      ) {
        const group =
          addClusteredPoints(
            items,
            sellerIcon,
            (item) => `
              <strong>Seller</strong>
              <br/>
              ID: ${popupValue(item.seller_id)}
              <br/>
              ${popupValue(item.city)}, ${popupValue(item.state)}
            `,
          )

        layerRefs.current[name] =
          group

        group.addTo(map)
      }

      if (
        name === 'orders'
      ) {
        const group =
          addClusteredPoints(
            items,
            L.divIcon({
              className:
                'order-marker',
              html:
                '<span>O</span>',
              iconSize: [
                12,
                12,
              ],
              iconAnchor: [
                6,
                6,
              ],
            }),
            (item) => `
              <strong>Order</strong>
              <br/>
              ID: ${popupValue(item.order_id)}
              <br/>
              Status: ${popupValue(item.order_status)}
              <br/>
              Purchase: ${popupValue(item.purchase_date)}
            `,
          )

        layerRefs.current[name] =
          group

        group.addTo(map)
      }

      if (
        name === 'demand'
      ) {
        const heat =
          addHeatmap(
            items,
            (item) =>
              Number(
                item.forecast_7d,
              ) || 0,
          )

        layerRefs.current[name] =
          heat

        heat.addTo(map)
      }

      if (
        name === 'inventory'
      ) {
        const heat =
          addHeatmap(
            items,
            (item) =>
              Number(
                item.available_inventory,
              ) || 0,
          )

        layerRefs.current[name] =
          heat

        heat.addTo(map)
      }

      if (
        name === 'delivery'
      ) {
        const heat =
          addHeatmap(
            items,
            (item) =>
              Number(
                item.late_delivery_probability,
              ) || 0,
          )

        layerRefs.current[name] =
          heat

        heat.addTo(map)
      }

      if (
        name === 'transfers'
      ) {
        const group =
          L.layerGroup()

        filtered(items).forEach(
          (item) => {
            const originLat =
              Number(
                item.origin_latitude,
              )

            const originLng =
              Number(
                item.origin_longitude,
              )

            const destinationLat =
              Number(
                item.destination_latitude,
              )

            const destinationLng =
              Number(
                item.destination_longitude,
              )

            if (
              !Number.isFinite(
                originLat,
              ) ||
              !Number.isFinite(
                originLng,
              ) ||
              !Number.isFinite(
                destinationLat,
              ) ||
              !Number.isFinite(
                destinationLng,
              )
            ) {
              return
            }

            L.polyline(
              [
                [
                  originLat,
                  originLng,
                ],
                [
                  destinationLat,
                  destinationLng,
                ],
              ],
              {
                weight: 3,
                opacity: 0.65,
              },
            )
              .bindPopup(
                network === 'india'
                  ? `
                <strong>India Warehouse Transfer</strong>
                <br/>
                ${popupValue(item.transfer_id)}
                <br/>
                ${popupValue(item.source_warehouse_id ?? item.origin)}
                → ${popupValue(item.destination_warehouse_id ?? item.destination)}
                <br/>
                Product: ${popupValue(item.product_id)}
                <br/>
                Quantity: ${Number(
                  item.quantity ?? 0,
                ).toFixed(2)}
                <br/>
                Distance: ${Number(
                  item.distance_km ?? 0,
                ).toFixed(1)} km
                `
                  : `
                <strong>Synthetic Warehouse Transfer</strong>
                <br/>
                ${popupValue(item.transfer_id)}
                <br/>
                ${popupValue(item.source_warehouse_id ?? item.origin)}
                → ${popupValue(item.destination_warehouse_id ?? item.destination)}
                <br/>
                Product: ${popupValue(item.product_id)}
                <br/>
                Quantity: ${Number(
                  item.quantity ?? 0,
                ).toFixed(2)}
                <br/>
                Distance: ${Number(
                  item.distance_km ?? 0,
                ).toFixed(1)} km
                `,
              )
              .addTo(group)
          },
        )

        layerRefs.current[name] =
          group

        group.addTo(map)
      }

      if (
        name === 'routes'
      ) {
        const group =
          L.layerGroup()

        items.forEach((item) => {
          const originLat =
            Number(
              item.origin_latitude,
            )

          const originLng =
            Number(
              item.origin_longitude,
            )

          const destinationLat =
            Number(
              item.destination_latitude,
            )

          const destinationLng =
            Number(
              item.destination_longitude,
            )

          if (
            !Number.isFinite(
              originLat,
            ) ||
            !Number.isFinite(
              originLng,
            ) ||
            !Number.isFinite(
              destinationLat,
            ) ||
            !Number.isFinite(
              destinationLng,
            )
          ) {
            return
          }

          L.polyline(
            [
              [
                originLat,
                originLng,
              ],
              [
                destinationLat,
                destinationLng,
              ],
            ],
            {
              weight: 1,
              opacity: 0.25,
              dashArray:
                '5 5',
            },
          )
            .bindPopup(
              network === 'india'
                ? `
              <strong>India Warehouse Route</strong>
              <br/>
              ${popupValue(item.origin_warehouse_id)}
              → ${popupValue(item.destination_warehouse_id)}
              <br/>
              ${popupValue(item.origin_city)}
              →
              ${popupValue(item.destination_city)}
              <br/>
              Distance: ${Number(
                item.distance_km ?? 0,
              ).toFixed(1)} km
              `
                : `
              <strong>Synthetic Warehouse Route</strong>
              <br/>
              ${popupValue(item.origin_warehouse_id)}
              → ${popupValue(item.destination_warehouse_id)}
              <br/>
              ${popupValue(item.origin_city)}
              →
              ${popupValue(item.destination_city)}
              <br/>
              Distance: ${Number(
                item.distance_km ?? 0,
              ).toFixed(1)} km
              `,
            )
            .addTo(group)
        })

        layerRefs.current[name] =
          group

        group.addTo(map)
      }

      if (name === 'shipping_lanes') {
        const group =
          L.layerGroup()

        const bounds =
          L.latLngBounds([])

        items.forEach((item) => {
          const originLat =
            Number(
              item.origin_latitude,
            )

          const originLng =
            Number(
              item.origin_longitude,
            )

          const destinationLat =
            Number(
              item.destination_latitude,
            )

          const destinationLng =
            Number(
              item.destination_longitude,
            )

          if (
            !Number.isFinite(
              originLat,
            ) ||
            !Number.isFinite(
              originLng,
            ) ||
            !Number.isFinite(
              destinationLat,
            ) ||
            !Number.isFinite(
              destinationLng,
            )
          ) {
            return
          }

          bounds.extend([
            originLat,
            originLng,
          ])

          bounds.extend([
            destinationLat,
            destinationLng,
          ])

          L.polyline(
            [
              [
                originLat,
                originLng,
              ],
              [
                destinationLat,
                destinationLng,
              ],
            ],
            {
              color: '#38bdf8',
              weight: 2,
              opacity: 0.7,
            },
          )
            .bindPopup(
              `
              <strong>Shipping Lane</strong>
              <br/>
              Seller: ${popupValue(item.seller_id)}
              <br/>
              ${popupValue(item.origin_city)}, ${popupValue(item.origin_state)}
              <br/>
              Customer: ${popupValue(item.customer_id)}
              <br/>
              ${popupValue(item.destination_city)}, ${popupValue(item.destination_state)}
              <br/>
              Order: ${popupValue(item.order_id)} #${popupValue(item.order_item_id)}
              <br/>
              Distance: ${Number(
                item.distance_km ?? 0,
              ).toFixed(1)} km
              `,
            )
            .addTo(group)
        })

        layerRefs.current[name] =
          group

        group.addTo(map)

        if (
          bounds.isValid() &&
          !shippingLaneFitRef.current
        ) {
          map.fitBounds(bounds, {
            padding: [40, 40],
            maxZoom: 6,
          })
          shippingLaneFitRef.current =
            true
        }
      }
    } catch (error) {
      if (
        signal?.aborted
      ) {
        return
      }

      setMapError(
        error instanceof Error
          ? error.message
          : 'Geospatial layer failed',
      )
    } finally {
      loadingCountRef.current = Math.max(
        0,
        loadingCountRef.current - 1,
      )
      if (loadingCountRef.current === 0) {
        setLoading(false)
      }
    }
  }

  React.useEffect(() => {
    if (!mapRef.current) {
      return
    }

    const map = L.map(
      mapRef.current,
    ).fitBounds(
      BRAZIL_BOUNDS,
      brazilViewOptions,
    )

    mapInstance.current =
      map

    L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        attribution:
          '© OpenStreetMap contributors',
        maxZoom: 18,
      },
    ).addTo(map)

    return () => {
      map.remove()
      mapInstance.current =
        null
      layerRefs.current = {}
    }
  }, [])

  React.useEffect(() => {
    layerAbortRef.current?.abort()
    const controller =
      new AbortController()
    layerAbortRef.current =
      controller

    const active = (
      Object.keys(
        layers,
      ) as LayerName[]
    ).filter((name) => layers[name])

    active.forEach((name) => {
      void loadLayer(
        name,
        controller.signal,
      )
    })

    // Clear any layers that were
    // toggled off so their markers
    // are removed from the map.
    ;(
      Object.keys(
        layers,
      ) as LayerName[]
    )
      .filter((name) => !layers[name])
      .forEach((name) => {
        clearLayer(name)
        if (name === 'shipping_lanes') {
          shippingLaneFitRef.current =
            false
        }
      })

    return () => {
      controller.abort()
    }
  }, [
    layers,
    filters.state,
    filters.city,
    network,
  ])

  const toggleLayer = (
    name: LayerName,
  ) => {
    setLayers((current) => ({
      ...current,
      [name]: !current[name],
    }))
  }

  const changeNetwork = (
    next: NetworkName,
  ) => {
    if (next === network) {
      return
    }

    setNetwork(next)
    setFilters({ state: '', city: '' })
    mapInstance.current?.fitBounds(
      next === 'india'
        ? INDIA_BOUNDS
        : BRAZIL_BOUNDS,
      brazilViewOptions,
    )
  }

  const resetFilters = () => {
    setFilters({
      state: '',
      city: '',
    })
  }

  const fitIndia = () => {
    mapInstance.current?.fitBounds(
      network === 'india'
        ? INDIA_BOUNDS
        : BRAZIL_BOUNDS,
      brazilViewOptions,
    )
  }

  return (
    <div className="map-shell">
      <div className="map-toolbar">
        <div className="filter-row">
          <select
            aria-label="Operational network"
            value={network}
            onChange={(event) =>
              changeNetwork(
                event.target.value as NetworkName,
              )
            }
          >
            <option value="brazil">
              Brazil · Synthetic Demo
            </option>
            <option value="india">
              India · Original Network
            </option>
          </select>

          <select
            value={filters.state}
            onChange={(event) =>
              setFilters(
                (current) => ({
                  ...current,
                  state:
                    event.target
                      .value,
                  city: '',
                }),
              )
            }
          >
            <option value="">
              All states
            </option>

            {filterOptions.states.map(
              (state) => (
                <option
                  key={state}
                  value={state}
                >
                  {state}
                </option>
              ),
            )}
          </select>

          <select
            value={filters.city}
            onChange={(event) =>
              setFilters(
                (current) => ({
                  ...current,
                  city:
                    event.target
                      .value,
                }),
              )
            }
          >
            <option value="">
              All cities
            </option>

            {filterOptions.cities.map(
              (city) => (
                <option
                  key={city}
                  value={city}
                >
                  {city}
                </option>
              ),
            )}
          </select>

          <button
            className="map-action"
            onClick={
              resetFilters
            }
          >
            Clear filters
          </button>

          <button
            className="map-action"
            onClick={fitIndia}
          >
            Reset map
          </button>
        </div>

        <div className="map-controls">
          {(
            Object.keys(
              layers,
            ) as LayerName[]
          ).map((name) => (
            <button
              key={name}
              className={
                layers[name]
                  ? 'map-toggle active'
                  : 'map-toggle'
              }
              onClick={() =>
                toggleLayer(
                  name,
                )
              }
            >
              {layerLabel(name, network)}
            </button>
          ))}
        </div>

        {loading && (
          <span className="map-status">
            Loading layer…
          </span>
        )}

        {mapError && (
          <span className="map-status">
            {mapError}
          </span>
        )}
      </div>

      <div
        ref={mapRef}
        className="map"
      />
    </div>
  )
}

function RegionAnalysis() {
  const [customers, setCustomers] =
    React.useState<Item[]>([])

  const [orders, setOrders] =
    React.useState<Item[]>([])

  const [delivery, setDelivery] =
    React.useState<Item[]>([])

  const [loading, setLoading] =
    React.useState(true)

  React.useEffect(() => {
    Promise.all([
      api(
        '/api/geospatial/customers?limit=10000',
      ),
      api(
        '/api/geospatial/orders?limit=10000',
      ),
      api(
        '/api/geospatial/delivery?limit=10000',
      ),
    ])
      .then(
        ([
          customerData,
          orderData,
          deliveryData,
        ]) => {
          setCustomers(
            customerData.items || [],
          )

          setOrders(
            orderData.items || [],
          )

          setDelivery(
            deliveryData.items || [],
          )
        },
      )
      .catch(() => undefined)
      .finally(() =>
        setLoading(false),
      )
  }, [])

  const regions =
    React.useMemo(() => {
      const map = new Map<
        string,
        {
          state: string
          customers: number
          orders: number
          deliveryRisk: number
          deliveryCount: number
        }
      >()

      customers.forEach(
        (item) => {
          const state = String(
            item.state ??
              'Unknown',
          )

          const existing =
            map.get(state) || {
              state,
              customers: 0,
              orders: 0,
              deliveryRisk: 0,
              deliveryCount: 0,
            }

          existing.customers += 1

          map.set(
            state,
            existing,
          )
        },
      )

      orders.forEach((item) => {
        const state = String(
          item.state ??
            item.customer_state ??
            'Unknown',
        )

        const existing =
          map.get(state) || {
            state,
            customers: 0,
            orders: 0,
            deliveryRisk: 0,
            deliveryCount: 0,
          }

        existing.orders += 1

        map.set(
          state,
          existing,
        )
      })

      delivery.forEach(
        (item) => {
          const state = String(
            item.state ??
              item.customer_state ??
              'Unknown',
          )

          const probability =
            Number(
              item.late_delivery_probability,
            )

          const existing =
            map.get(state) || {
              state,
              customers: 0,
              orders: 0,
              deliveryRisk: 0,
              deliveryCount: 0,
            }

          if (
            Number.isFinite(
              probability,
            )
          ) {
            existing.deliveryRisk +=
              probability

            existing.deliveryCount +=
              1
          }

          map.set(
            state,
            existing,
          )
        },
      )

      return Array.from(
        map.values(),
      )
        .map((item) => ({
          ...item,
          averageDeliveryRisk:
            item.deliveryCount >
            0
              ? item.deliveryRisk /
                item.deliveryCount
              : 0,
        }))
        .sort(
          (a, b) =>
            b.orders -
            a.orders,
        )
    }, [
      customers,
      orders,
      delivery,
    ])

  if (loading) {
    return (
      <div className="region-loading">
        Loading regional
        analysis…
      </div>
    )
  }

  return (
    <div className="region-analysis">
      <div className="analysis-grid">
        {regions
          .slice(0, 12)
          .map((region) => (
            <article
              className="region-card"
              key={region.state}
            >
              <strong>
                {region.state}
              </strong>

              <span>
                Customers:{' '}
                {region.customers.toLocaleString()}
              </span>

              <span>
                Orders:{' '}
                {region.orders.toLocaleString()}
              </span>

              <span>
                Avg delivery
                risk:{' '}
                {(
                  region.averageDeliveryRisk *
                  100
                ).toFixed(1)}
                %
              </span>
            </article>
          ))}
      </div>
    </div>
  )
}

export default function OlistControlTower({ onBack }: { onBack: () => void }) {
  const [tab, setTab] =
    React.useState(
      'Dashboard',
    )

  const [health, setHealth] =
    React.useState<Item | null>(
      null,
    )

  const [search, setSearch] =
    React.useState('')

  const [results, setResults] =
    React.useState<Item[]>([])

  const [data, setData] =
    React.useState<ApiResponse>({
      items: [],
      total: 0,
    })

  const [error, setError] =
    React.useState('')

  React.useEffect(() => {
    api('/api/health')
      .then(setHealth)
      .catch((e) =>
        setError(e.message),
      )
  }, [])

  React.useEffect(() => {
    const controller =
      new AbortController()
    const { signal } = controller

    const paths: Record<
      string,
      string
    > = {
      Optimization:
        '/api/optimization/results',
      'AI Insights':
        '/api/insights',
      Reports:
        '/api/reports',
    }

    if (tab === 'Settings') {
      setData({ items: [], total: 0 })
      return () => controller.abort()
    }

    const path = paths[tab]

    if (!path) {
      setData({
        items: [],
        total: 0,
      })
      return () => controller.abort()
    }

    api(path, signal)
      .then(setData)
      .catch((e) => {
        if (
          signal.aborted
        ) {
          return
        }
        setError(e.message)
      })

    return () => {
      controller.abort()
    }
  }, [tab])

  const doSearch = async () => {
    const query =
      search.trim()

    if (!query) {
      return
    }

    try {
      const response =
        await api(
          `/api/search?q=${encodeURIComponent(
            query,
          )}`,
        )

      setResults(
        response.items || [],
      )
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Search failed',
      )
    }
  }

  const openTab = (name: string) => {
    setTab((current) => current === name ? current : name)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="app">
      <aside>
        <div className="brand-header">
          <button className="back-btn" onClick={onBack}>
            ← Home
          </button>
          <div className="brand">
            Supply
            <span>Sphere</span>
            <small>
              CONTROL TOWER
            </small>
          </div>
        </div>

        {[
          'Dashboard',
          'Demand Forecast',
          'Inventory',
          'Warehouses',
          'Suppliers',
          'Logistics',
          'Geospatial',
          'Optimization',
          'AI Insights',
          'Reports',
          'Settings',
        ].map((name) => (
          <button
            className={
              tab === name
                ? 'active'
                : ''
            }
            onClick={() =>
              setTab(name)
            }
            key={name}
          >
            {name}
          </button>
        ))}
      </aside>

      <main>
        <header>
          <div>
            <div className="eyebrow">
              OLIST CONTROL TOWER · ENTERPRISE SUPPLY CHAIN INTELLIGENCE
            </div>

            <h1>{tab}</h1>

            <p>
              Real Olist history + deterministic operational network
            </p>
          </div>

          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span className="ct-risk-badge low" style={{ fontVariantNumeric: 'tabular-nums' }}>
              ● LIVE
            </span>
            <div className="search">
              <input
                placeholder="Search order, SKU, seller, supplier, warehouse…"
                value={search}
                onChange={(event) =>
                  setSearch(
                    event.target.value,
                  )
                }
                onKeyDown={(
                  event,
                ) => {
                  if (
                    event.key ===
                    'Enter'
                  ) {
                    void doSearch()
                  }
                }}
              />

              <button
                onClick={() =>
                  void doSearch()
                }
              >
                Search
              </button>
            </div>
          </div>
        </header>

        {error && (
          <div className="error">
            {error}
          </div>
        )}

        {results.length >
          0 && (
          <div className="results">
            {results.map(
              (
                result,
                index,
              ) => (
                <div
                  key={
                    index
                  }
                >
                  <b>
                    {popupValue(
                      result.type,
                    )}
                  </b>

                  {' · '}

                  {popupValue(
                    result.label,
                  )}

                  {result.risk_level
                    ? ` · ${popupValue(
                        result.risk_level,
                      )}`
                    : ''}
                </div>
              ),
            )}
          </div>
        )}

        {tab ===
          'Dashboard' && (
          <DashboardView onOpenTab={openTab} />
        )}

        {tab ===
          'Geospatial' && (
          <>
            <section className="panel">
              <div className="table-head">
                <div>
                  <h2>
                    Geospatial
                    Control
                    Tower
                  </h2>

                  <p>
                    Layers,
                    clustering,
                    heatmaps
                    and
                    geographic
                    filtering
                  </p>
                </div>
              </div>

              <MapView />
            </section>

            <section className="panel">
              <h2>
                Regional
                analysis
              </h2>

              <RegionAnalysis />
            </section>

            <section className="panel">
              <h2>
                Geospatial
                data
                integrity
              </h2>

              <p>
                Customer and
                seller
                coordinates
                are resolved
                from the
                Olist
                ZIP-prefix
                geolocation
                dataset.
                Supplier
                coordinates
                are not
                fabricated
                because the
                supplied
                supplier
                dataset
                does not
                contain
                geographic
                fields.
              </p>
            </section>
          </>
        )}

        {tab === 'Optimization' && isOptimizationResult(data) && (
          <section className="panel">
            <div className="table-head">
              <h2>Optimization Results</h2>
            </div>

            <div className="optimization-grid">
              <article className="opt-card">
                <h3>Solver Status</h3>
                <div className="opt-value">{data.solver || 'N/A'}</div>
                <div className="opt-sub">{data.status || 'N/A'}</div>
              </article>

              <article className="opt-card">
                <h3>Current Cost</h3>
                <div className="opt-value">
                  {data.current_cost != null
                    ? '$' + Number(data.current_cost).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                    : 'N/A'}
                </div>
              </article>

              <article className="opt-card">
                <h3>Optimized Cost</h3>
                <div className="opt-value">
                  {data.optimized_cost != null
                    ? '$' + Number(data.optimized_cost).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                    : 'N/A'}
                </div>
              </article>

              <article className="opt-card">
                <h3>Estimated Savings</h3>
                <div className="opt-value savings">
                  {data.estimated_savings != null
                    ? '$' + Number(data.estimated_savings).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                    : 'N/A'}
                </div>
              </article>

              <article className="opt-card">
                <h3>Service Level</h3>
                <div className="opt-value">
                  {data.service_level != null
                    ? (Number(data.service_level) * 100).toFixed(2) + '%'
                    : 'N/A'}
                </div>
              </article>

              <article className="opt-card">
                <h3>Stockout Risk</h3>
                <div className="opt-value">
                  {data.stockout_risk != null
                    ? (Number(data.stockout_risk) * 100).toFixed(2) + '%'
                    : 'N/A'}
                </div>
              </article>
            </div>

            <div className="opt-details">
              <h4>Operational Details</h4>
              <div className="opt-detail-grid">
                {data.warehouse_rows != null && (
                  <div className="opt-detail">
                    <span className="opt-label">Warehouse Rows</span>
                    <span className="opt-value">{data.warehouse_rows}</span>
                  </div>
                )}
                {data.transfer_rows != null && (
                  <div className="opt-detail">
                    <span className="opt-label">Transfer Rows</span>
                    <span className="opt-value">{data.transfer_rows}</span>
                  </div>
                )}
                {data.supplier_rows != null && (
                  <div className="opt-detail">
                    <span className="opt-label">Supplier Rows</span>
                    <span className="opt-value">{data.supplier_rows}</span>
                  </div>
                )}
                {data.supplier_count != null && (
                  <div className="opt-detail">
                    <span className="opt-label">Unique Suppliers</span>
                    <span className="opt-value">{data.supplier_count}</span>
                  </div>
                )}
                {data.warehouse_count != null && (
                  <div className="opt-detail">
                    <span className="opt-label">Warehouses</span>
                    <span className="opt-value">{data.warehouse_count}</span>
                  </div>
                )}
                {data.demand_rows != null && (
                  <div className="opt-detail">
                    <span className="opt-label">Demand Rows</span>
                    <span className="opt-value">{data.demand_rows.toLocaleString()}</span>
                  </div>
                )}
                {data.inventory_rows != null && (
                  <div className="opt-detail">
                    <span className="opt-label">Inventory Rows</span>
                    <span className="opt-value">{data.inventory_rows.toLocaleString()}</span>
                  </div>
                )}
                {data.demand_snapshot_date && (
                  <div className="opt-detail">
                    <span className="opt-label">Demand Snapshot</span>
                    <span className="opt-value">{data.demand_snapshot_date}</span>
                  </div>
                )}
                {data.time_limit_ms != null && (
                  <div className="opt-detail">
                    <span className="opt-label">Solver Time Limit</span>
                    <span className="opt-value">{data.time_limit_ms} ms</span>
                  </div>
                )}
              </div>
            </div>

            {Object.keys(data).length === 0 && (
              <div className="opt-empty">
                No optimization results available. Run optimization via POST /api/optimization/run.
              </div>
            )}
          </section>
        )}

        {tab === 'AI Insights' && isInsightsResponse(data) && (
          <section className="panel">
            <div className="table-head">
              <h2>Operational Insights</h2>
              <span className="insights-meta">
                {data.generated_at && (
                  <>
                    Updated: {new Date(data.generated_at).toLocaleString()}
                  </>
                )}
              </span>
            </div>

            {data.items.length === 0 ? (
              <div className="insights-empty">No insights available</div>
            ) : (
              <div className="insights-grid">
                {data.items.map((insight, index) => (
                  <article
                    key={index}
                    className={`insight-card severity-${insight.severity}`}
                  >
                    <div className="insight-header">
                      <span className="insight-category">{insight.category}</span>
                      <span className={`insight-severity ${insight.severity}`}>
                        {insight.severity.toUpperCase()}
                      </span>
                    </div>
                    <h3 className="insight-title">{insight.title}</h3>
                    <p className="insight-description">{insight.description}</p>
                    <div className="insight-action">
                      <span className="action-label">Recommended Action:</span>
                      <span className="action-text">{insight.action}</span>
                    </div>
                    {insight.count > 0 && (
                      <div className="insight-count">{insight.count} affected</div>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {tab === 'Reports' && isReportResponse(data) && (
          <section className="panel">
            <div className="table-head">
              <h2>Operational Reports</h2>
              <span className="reports-meta">
                {data.generated_at && (
                  <>
                    Generated: {new Date(data.generated_at).toLocaleString()}
                  </>
                )}
              </span>
            </div>

            <div className="reports-grid">
              <article className="report-section">
                <h3>Executive Summary</h3>
                <div className="report-cards">
                  {data.summary?.revenue != null && (
                    <div className="report-card">
                      <span className="report-label">Revenue</span>
                      <span className="report-value">${Number(data.summary.revenue).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
                    </div>
                  )}
                  {data.summary?.orders != null && (
                    <div className="report-card">
                      <span className="report-label">Orders</span>
                      <span className="report-value">{Number(data.summary.orders).toLocaleString()}</span>
                    </div>
                  )}
                  {data.inventory_risk?.total_at_risk != null && (
                    <div className="report-card risk">
                      <span className="report-label">Inventory at Risk</span>
                      <span className="report-value">{data.inventory_risk.total_at_risk}</span>
                      <span className="report-sub">High: {data.inventory_risk.high} · Critical: {data.inventory_risk.critical}</span>
                    </div>
                  )}
                  {data.delivery_risk?.total_at_risk != null && (
                    <div className="report-card risk">
                      <span className="report-label">Delivery at Risk</span>
                      <span className="report-value">{data.delivery_risk.total_at_risk}</span>
                      <span className="report-sub">High: {data.delivery_risk.high} · Critical: {data.delivery_risk.critical}</span>
                    </div>
                  )}
                  {data.supplier_risk?.total_at_risk != null && (
                    <div className="report-card risk">
                      <span className="report-label">Suppliers at Risk</span>
                      <span className="report-value">{data.supplier_risk.total_at_risk}</span>
                      <span className="report-sub">High: {data.supplier_risk.high} · Critical: {data.supplier_risk.critical}</span>
                    </div>
                  )}
                </div>
              </article>

              <article className="report-section">
                <h3>Inventory Operations</h3>
                <div className="report-cards">
                  {data.operational_metrics?.latest_snapshot_date && (
                    <div className="report-card">
                      <span className="report-label">Latest Snapshot</span>
                      <span className="report-value">{data.operational_metrics.latest_snapshot_date}</span>
                    </div>
                  )}
                  {data.operational_metrics?.total_on_hand != null && (
                    <div className="report-card">
                      <span className="report-label">Total On-Hand</span>
                      <span className="report-value">{Number(data.operational_metrics.total_on_hand).toLocaleString()}</span>
                    </div>
                  )}
                  {data.operational_metrics?.zero_stock_skus != null && (
                    <div className="report-card risk">
                      <span className="report-label">Zero Stock SKUs</span>
                      <span className="report-value">{data.operational_metrics.zero_stock_skus}</span>
                    </div>
                  )}
                  {data.operational_metrics?.unique_products != null && (
                    <div className="report-card">
                      <span className="report-label">Unique Products</span>
                      <span className="report-value">{data.operational_metrics.unique_products}</span>
                    </div>
                  )}
                  {data.operational_metrics?.unique_warehouses != null && (
                    <div className="report-card">
                      <span className="report-label">Active Warehouses</span>
                      <span className="report-value">{data.operational_metrics.unique_warehouses}</span>
                    </div>
                  )}
                </div>
              </article>

              <article className="report-section">
                <h3>Forecast Performance</h3>
                <div className="report-cards">
                  {data.forecast_performance?.selected_model && (
                    <div className="report-card">
                      <span className="report-label">Selected Model</span>
                      <span className="report-value">{data.forecast_performance.selected_model}</span>
                    </div>
                  )}
                  {data.forecast_performance?.accuracy != null && (
                    <div className="report-card">
                      <span className="report-label">Forecast Accuracy</span>
                      <span className="report-value">{(Number(data.forecast_performance.accuracy) * 100).toFixed(2)}%</span>
                    </div>
                  )}
                  {data.forecast_performance?.wape != null && (
                    <div className="report-card">
                      <span className="report-label">WAPE</span>
                      <span className="report-value">{Number(data.forecast_performance.wape).toFixed(6)}</span>
                    </div>
                  )}
                  {data.forecast_performance?.smape != null && (
                    <div className="report-card">
                      <span className="report-label">sMAPE</span>
                      <span className="report-value">{Number(data.forecast_performance.smape).toFixed(6)}</span>
                    </div>
                  )}
                  {data.forecast_performance?.mae != null && (
                    <div className="report-card">
                      <span className="report-label">MAE</span>
                      <span className="report-value">{Number(data.forecast_performance.mae).toFixed(6)}</span>
                    </div>
                  )}
                  {data.forecast_performance?.rmse != null && (
                    <div className="report-card">
                      <span className="report-label">RMSE</span>
                      <span className="report-value">{Number(data.forecast_performance.rmse).toFixed(6)}</span>
                    </div>
                  )}
                </div>
              </article>

              <article className="report-section">
                <h3>Optimization Result</h3>
                <div className="report-cards">
                  {data.optimization_result?.solver && (
                    <div className="report-card">
                      <span className="report-label">Solver</span>
                      <span className="report-value">{data.optimization_result.solver}</span>
                    </div>
                  )}
                  {data.optimization_result?.status && (
                    <div className="report-card">
                      <span className="report-label">Status</span>
                      <span className="report-value">{data.optimization_result.status}</span>
                    </div>
                  )}
                  {data.optimization_result?.current_cost != null && (
                    <div className="report-card">
                      <span className="report-label">Current Cost</span>
                      <span className="report-value">${Number(data.optimization_result.current_cost).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
                    </div>
                  )}
                  {data.optimization_result?.optimized_cost != null && (
                    <div className="report-card">
                      <span className="report-label">Optimized Cost</span>
                      <span className="report-value">${Number(data.optimization_result.optimized_cost).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
                    </div>
                  )}
                  {data.optimization_result?.estimated_savings != null && (
                    <div className="report-card savings">
                      <span className="report-label">Estimated Savings</span>
                      <span className="report-value">${Number(data.optimization_result.estimated_savings).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
                    </div>
                  )}
                  {data.optimization_result?.service_level != null && (
                    <div className="report-card">
                      <span className="report-label">Service Level</span>
                      <span className="report-value">{(Number(data.optimization_result.service_level) * 100).toFixed(2)}%</span>
                    </div>
                  )}
                  {data.optimization_result?.stockout_risk != null && (
                    <div className="report-card">
                      <span className="report-label">Stockout Risk</span>
                      <span className="report-value">{(Number(data.optimization_result.stockout_risk) * 100).toFixed(2)}%</span>
                    </div>
                  )}
                  {data.optimization_result?.transfers_recommended != null && (
                    <div className="report-card">
                      <span className="report-label">Transfers Recommended</span>
                      <span className="report-value">{data.optimization_result.transfers_recommended}</span>
                    </div>
                  )}
                </div>
              </article>
            </div>

            {Object.keys(data).length === 0 && (
              <div className="reports-empty">No report data available</div>
            )}
          </section>
        )}

        {tab === 'Demand Forecast' && (
          <OperativeTable
            title="Demand Forecast"
            subtitle="Product-level demand estimates derived from the daily demand history."
            endpoint="/api/demand/forecast?limit=500"
            columns={[
              { key: 'product_id', label: 'Product ID' },
              { key: 'demand_7d', label: 'Demand (7d)', format: (v) => fmtNum(v) },
              { key: 'demand_30d', label: 'Demand (30d)', format: (v) => fmtNum(v) },
            ]}
            searchKeys={['product_id']}
            searchPlaceholder="Search product ID…"
          />
        )}

        {tab === 'Inventory' && (
          <OperativeTable
            title="Inventory"
            subtitle="Stockout probabilities, days of cover, and warehouse-level risk exposure."
            endpoint="/api/inventory?limit=500"
            columns={[
              { key: 'warehouse_id', label: 'Warehouse' },
              { key: 'product_id', label: 'Product ID' },
              { key: 'risk_level', label: 'Risk', render: (v) => <RiskBadge value={v} /> },
              { key: 'stockout_probability', label: 'Stockout Probability', format: (v) => fmtPct(v, 2) },
              { key: 'days_of_cover', label: 'Days of Cover', format: (v) => fmtNum(v) },
              { key: 'expected_stockout_date', label: 'Expected Stockout', format: (v) => v ? String(v) : '—' },
            ]}
            searchKeys={['warehouse_id', 'product_id']}
            searchPlaceholder="Search warehouse or product ID…"
            riskable={{ key: 'risk_level', levels: ['Low', 'Medium', 'High', 'Critical'] }}
          />
        )}

        {tab === 'Warehouses' && (
          <OperativeTable
            title="Warehouses"
            subtitle="Network warehouse geography, capacity, and operating cost per unit."
            endpoint="/api/warehouses?limit=500"
            columns={[
              { key: 'warehouse_id', label: 'Warehouse ID' },
              { key: 'city', label: 'City' },
              { key: 'latitude', label: 'Latitude', format: (v) => Number(v).toFixed(4) },
              { key: 'longitude', label: 'Longitude', format: (v) => Number(v).toFixed(4) },
              { key: 'capacity_units', label: 'Capacity (units)', format: (v) => fmtNum(v) },
              { key: 'operating_cost_per_unit', label: 'Op Cost / Unit', format: (v) => fmtMoney(v) },
            ]}
            searchKeys={['warehouse_id', 'city']}
            searchPlaceholder="Search warehouse or city…"
          />
        )}

        {tab === 'Suppliers' && (
          <OperativeTable
            title="Suppliers"
            subtitle="Supplier intelligence: lead times, reliability, cost, scoring, and risk drivers."
            endpoint="/api/suppliers?limit=500"
            columns={[
              { key: 'supplier_id', label: 'Supplier ID' },
              { key: 'supplier_name', label: 'Name' },
              { key: 'risk_level', label: 'Risk', render: (v) => <RiskBadge value={v} /> },
              { key: 'reliability', label: 'Reliability', format: (v) => fmtPct(v, 1) },
              { key: 'lead_time_days', label: 'Lead Time (days)', format: (v) => fmtNum(v) },
              { key: 'unit_cost', label: 'Unit Cost', format: (v) => fmtMoney(v) },
              { key: 'on_time_delivery_rate', label: 'On-Time Rate', format: (v) => fmtPct(v, 1) },
              { key: 'defect_rate', label: 'Defect Rate', format: (v) => fmtPct(v, 1) },
            ]}
            searchKeys={['supplier_id', 'supplier_name']}
            searchPlaceholder="Search supplier ID or name…"
            riskable={{ key: 'risk_level', levels: ['Low', 'Medium', 'High', 'Critical'] }}
          />
        )}

        {tab === 'Logistics' && (
          <OperativeTable
            title="Logistics"
            subtitle="Delivery risk predictions with late-delivery probability per order."
            endpoint="/api/logistics/delivery-risk?limit=500"
            columns={[
              { key: 'order_id', label: 'Order ID' },
              { key: 'risk_level', label: 'Risk', render: (v) => <RiskBadge value={v} /> },
              { key: 'late_delivery_probability', label: 'Late Delivery Probability', format: (v) => fmtPct(v, 2) },
              { key: 'expected_delivery_date', label: 'Expected Delivery', format: (v) => v ? String(v) : '—' },
            ]}
            searchKeys={['order_id']}
            searchPlaceholder="Search order ID…"
            riskable={{ key: 'risk_level', levels: ['Low', 'Medium', 'High', 'Critical'] }}
          />
        )}

        {tab === 'Settings' && (
          <section className="panel">
            <div className="table-head">
              <h2>Settings</h2>
            </div>

            <div className="settings-grid">
              <article className="settings-section">
                <h3>Application</h3>
                <dl className="settings-list">
                  <div className="setting-item">
                    <dt>Environment</dt>
                    <dd>{(health?.environment as string) || 'Unknown'}</dd>
                  </div>
                  <div className="setting-item">
                    <dt>API Version</dt>
                    <dd>{(health?.api_version as string) || 'Unknown'}</dd>
                  </div>
                  <div className="setting-item">
                    <dt>Phases</dt>
                    <dd>{(health?.phases as string) || 'Unknown'}</dd>
                  </div>
                </dl>
              </article>

              <article className="settings-section">
                <h3>API Status</h3>
                <dl className="settings-list">
                  <div className="setting-item">
                    <dt>API Connection</dt>
                    <dd className="status-ok">Connected</dd>
                  </div>
                  <div className="setting-item">
                    <dt>Components</dt>
                    <dd>{(health?.components as string[] | undefined)?.join(', ') || 'Unknown'}</dd>
                  </div>
                </dl>
              </article>

              <article className="settings-section">
                <h3>Realtime Engine</h3>
                <dl className="settings-list">
                  <div className="setting-item">
                    <dt>Status Endpoint</dt>
                    <dd><code>/api/realtime/status</code></dd>
                  </div>
                  <div className="setting-item">
                    <dt>Control</dt>
                    <dd>Start / Pause / Stop / Tick via POST</dd>
                  </div>
                  <div className="setting-item">
                    <dt>Event Stream</dt>
                    <dd><code>/api/realtime/stream</code> (SSE)</dd>
                  </div>
                </dl>
              </article>

              <article className="settings-section">
                <h3>MLOps</h3>
                <dl className="settings-list">
                  <div className="setting-item">
                    <dt>Models Endpoint</dt>
                    <dd><code>/api/mlops/models</code></dd>
                  </div>
                  <div className="setting-item">
                    <dt>Health Endpoint</dt>
                    <dd><code>/api/mlops/health</code></dd>
                  </div>
                  <div className="setting-item">
                    <dt>Registry</dt>
                    <dd>Local filesystem (MLflow optional)</dd>
                  </div>
                </dl>
              </article>

              <article className="settings-section">
                <h3>Data Sources</h3>
                <dl className="settings-list">
                  <div className="setting-item">
                    <dt>Processed Data Directory</dt>
                    <dd><code>{import.meta.env.VITE_DATA_DIR || 'data/processed'}</code></dd>
                  </div>
                  <div className="setting-item">
                    <dt>Primary Datasets</dt>
                    <dd>Olist Brazilian E-commerce (public)</dd>
                  </div>
                  <div className="setting-item">
                    <dt>Derived Artifacts</dt>
                    <dd>Stockout predictions, Supplier intelligence, Delivery risk, Demand forecasts, Optimization results</dd>
                  </div>
                </dl>
              </article>

              <article className="settings-section">
                <h3>API Endpoints Reference</h3>
                <dl className="settings-list">
                  <div className="setting-item">
                    <dt>Operations</dt>
                    <dd>/api/inventory, /api/suppliers, /api/warehouses, /api/logistics/delivery-risk, /api/search</dd>
                  </div>
                  <div className="setting-item">
                    <dt>Optimization</dt>
                    <dd>POST /api/optimization/run, GET /api/optimization/results</dd>
                  </div>
                  <div className="setting-item">
                    <dt>Insights & Reports</dt>
                    <dd>GET /api/insights, GET /api/reports</dd>
                  </div>
                  <div className="setting-item">
                    <dt>Geospatial</dt>
                    <dd>/api/geospatial/* (warehouses, customers, orders, inventory, delivery, transfers, routes)</dd>
                  </div>
                  <div className="setting-item">
                    <dt>Dashboard</dt>
                    <dd>GET /api/dashboard/summary</dd>
                  </div>
                  <div className="setting-item">
                    <dt>Health</dt>
                    <dd>GET /api/health</dd>
                  </div>
                </dl>
              </article>
            </div>

            <div className="settings-footer">
              <p>Settings are informational. No persistent configuration is stored in the frontend.</p>
            </div>
          </section>
        )}

        {tab !==
          'Dashboard' &&
          tab !==
            'Demand Forecast' &&
          tab !==
            'Inventory' &&
          tab !==
            'Warehouses' &&
          tab !==
            'Suppliers' &&
          tab !==
            'Logistics' &&
          tab !==
            'Geospatial' &&
          tab !==
            'Optimization' &&
          tab !==
            'AI Insights' &&
          tab !==
            'Reports' &&
          tab !==
            'Settings' && isPage(data) && (
            <section className="panel">
              <div className="table-head">
                <h2>
                  {tab} data
                </h2>

                <span>
                  {
                    data.total
                  }{' '}
                  records
                </span>
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      {Object.keys(
                        data
                          .items[0] ||
                          {},
                      )
                        .slice(
                          0,
                          7,
                        )
                        .map(
                          (
                            key,
                          ) => (
                            <th
                              key={
                                key
                              }
                            >
                              {
                                key
                              }
                            </th>
                          ),
                        )}
                    </tr>
                  </thead>

                  <tbody>
                    {data.items.map(
                      (
                        row: Item,
                        index: number,
                      ) => (
                        <tr
                          key={
                            index
                          }
                        >
                          {Object.keys(
                            row,
                          )
                            .slice(
                              0,
                              7,
                            )
                            .map(
                              (
                                key,
                              ) => (
                                <td
                                  key={
                                    key
                                  }
                                >
                                  {popupValue(
                                    row[
                                      key
                                    ],
                                  )}
                                </td>
                              ),
                            )}
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}
      </main>
    </div>
  )
}
