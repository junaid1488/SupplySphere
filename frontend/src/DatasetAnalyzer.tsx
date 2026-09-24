import React from 'react'

const api = async (path: string, init?: RequestInit) => {
  const response = await fetch(path, init)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: `${response.status} ${response.statusText}` }))
    throw new Error(err.detail || `${response.status} ${response.statusText}`)
  }
  return response.json()
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

type SessionMeta = {
  dataset_id: string
  original_filename: string
  file_format: string
  file_size_bytes: number
  status: string
  row_count: number | null
  column_count: number | null
  created_at: string
  expires_at: string
}

type SectionState = {
  loading: boolean
  data: any
  error: string
}

function LoadingState({ label }: { label: string }) {
  return <div className="ds-loading"><div className="ds-spinner" /> Loading {label}...</div>
}

function ErrorState({ message }: { message: string }) {
  return <div className="ds-error">{message}</div>
}

function EmptyState({ message }: { message: string }) {
  return <div className="ds-empty">{message}</div>
}

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="ds-section-header">
      <h3>{title}</h3>
      {subtitle && <p>{subtitle}</p>}
    </div>
  )
}

function CapabilityBadge({ name, status, detected_fields }: { name: string; status: string; detected_fields: string[] }) {
  const isAvailable = status === 'available'
  return (
    <span className={`ds-capability-badge ${isAvailable ? 'ds-cap-available' : 'ds-cap-unavailable'}`}>
      {name.replace(/_/g, ' ')}
      {isAvailable && detected_fields.length > 0 && (
        <small> ({detected_fields.length} fields)</small>
      )}
    </span>
  )
}

function KVRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="ds-kv">
      <span className="ds-kv-label">{label}</span>
      <span className="ds-kv-value">{value ?? '—'}</span>
    </div>
  )
}

function MiniTable({ columns, rows, maxRows = 20 }: { columns: string[]; rows: any[]; maxRows?: number }) {
  const displayRows = rows.slice(0, maxRows)
  return (
    <div className="ds-table-wrap">
      <table>
        <thead>
          <tr>{columns.map(c => <th key={c}>{c}</th>)}</tr>
        </thead>
        <tbody>
          {displayRows.map((row, i) => (
            <tr key={i}>{columns.map(c => <td key={c}>{String(row[c] ?? '')}</td>)}</tr>
          ))}
        </tbody>
      </table>
      {rows.length > maxRows && <div className="ds-table-more">Showing {maxRows} of {rows.length} rows</div>}
    </div>
  )
}

type SectionId = 'overview' | 'kpis' | 'analytics' | 'trends' | 'domain' | 'geospatial' | 'routes' | 'anomalies' | 'ask' | 'insights' | 'report'

const SECTION_NAV: Array<{ id: SectionId; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'kpis', label: 'KPIs' },
  { id: 'analytics', label: 'Analytics' },
  { id: 'trends', label: 'Trends' },
  { id: 'domain', label: 'Domain' },
  { id: 'geospatial', label: 'Geospatial' },
  { id: 'routes', label: 'Routes' },
  { id: 'anomalies', label: 'Anomalies' },
  { id: 'ask', label: 'Ask' },
  { id: 'insights', label: 'Insights' },
  { id: 'report', label: 'Report' },
]

const SECTION_ENDPOINTS: Partial<Record<SectionId, string>> = {
  kpis: 'kpis',
  analytics: 'analytics',
  trends: 'trends',
  domain: 'domain',
  geospatial: 'geospatial',
  routes: 'routes',
  anomalies: 'anomalies',
  insights: 'insights',
  report: 'report',
}

export default function DatasetAnalyzer() {
  const [sessions, setSessions] = React.useState<SessionMeta[]>([])
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null)
  const [uploading, setUploading] = React.useState(false)
  const [uploadError, setUploadError] = React.useState('')
  const [deletingId, setDeletingId] = React.useState<string | null>(null)
  const [activeSession, setActiveSession] = React.useState<string | null>(null)
  const [activeSection, setActiveSection] = React.useState<SectionId>('overview')
  const [activeStatus, setActiveStatus] = React.useState<string | null>(null)
  const [activeErrorMsg, setActiveErrorMsg] = React.useState('')

  const [sections, setSections] = React.useState<Record<string, SectionState>>({})
  const sectionsRef = React.useRef<Record<string, SectionState>>({})
  const setSection = (key: string, value: SectionState) => {
    sectionsRef.current = { ...sectionsRef.current, [key]: value }
    setSections(sectionsRef.current)
  }

  const [queries, setQueries] = React.useState<SectionState>({ loading: false, data: null, error: '' })
  const queriesRef = React.useRef<SectionState>(queries)
  const setQueriesState = (value: SectionState) => {
    queriesRef.current = value
    setQueries(value)
  }

  const [askQuestion, setAskQuestion] = React.useState('')
  const [askResult, setAskResult] = React.useState<SectionState>({ loading: false, data: null, error: '' })
  const [askHistory, setAskHistory] = React.useState<Array<{ question: string; result: any }>>([])

  const loadSessions = React.useCallback(async () => {
    try {
      const data = await api('/api/dataset-analyzer/sessions')
      setSessions(data.sessions || [])
    } catch (e) {
      console.error('Failed to load sessions:', e)
    }
  }, [])

  React.useEffect(() => { loadSessions() }, [loadSessions])

  const resetAllSections = () => {
    sectionsRef.current = {}
    setSections({})
    setQueriesState({ loading: false, data: null, error: '' })
    setAskResult({ loading: false, data: null, error: '' })
    setAskHistory([])
  }

  const fetchSectionOnce = React.useCallback(async (datasetId: string, sectionId: SectionId, endpoint: string) => {
    if (sectionsRef.current[sectionId]?.data || sectionsRef.current[sectionId]?.loading) return
    setSection(sectionId, { loading: true, data: null, error: '' })
    try {
      const data = await api(`/api/dataset-analyzer/sessions/${datasetId}/${endpoint}`)
      setSection(sectionId, { loading: false, data, error: '' })
    } catch (e: any) {
      setSection(sectionId, { loading: false, data: null, error: e.message || 'Failed to load' })
    }
  }, [])

  const fetchOverview = React.useCallback(async (datasetId: string) => {
    if (sectionsRef.current.overview?.data || sectionsRef.current.overview?.loading) return
    setSection('overview', { loading: true, data: null, error: '' })
    try {
      const [profile, schema, capabilities] = await Promise.all([
        api(`/api/dataset-analyzer/sessions/${datasetId}/profile`),
        api(`/api/dataset-analyzer/sessions/${datasetId}/schema`),
        api(`/api/dataset-analyzer/sessions/${datasetId}/capabilities`),
      ])
      setSection('overview', { loading: false, data: { profile, schema, capabilities }, error: '' })
    } catch (e: any) {
      setSection('overview', { loading: false, data: null, error: e.message || 'Failed to load' })
    }
  }, [])

  const fetchQueries = React.useCallback(async (datasetId: string) => {
    if (queriesRef.current.data || queriesRef.current.loading) return
    setQueriesState({ loading: true, data: null, error: '' })
    try {
      const data = await api(`/api/dataset-analyzer/sessions/${datasetId}/queries`)
      setQueriesState({ loading: false, data, error: '' })
    } catch (e: any) {
      setQueriesState({ loading: false, data: null, error: e.message || 'Failed to load' })
    }
  }, [])

  React.useEffect(() => {
    if (!activeSession || activeStatus !== 'ready') return
    const sectionId = activeSection
    if (sectionId === 'overview') {
      void fetchOverview(activeSession)
    } else if (sectionId === 'ask') {
      void fetchQueries(activeSession)
    } else {
      const endpoint = SECTION_ENDPOINTS[sectionId]
      if (endpoint) void fetchSectionOnce(activeSession, sectionId, endpoint)
    }
  }, [activeSession, activeStatus, activeSection, fetchOverview, fetchQueries, fetchSectionOnce])

  const loadSessionData = React.useCallback(async (datasetId: string) => {
    setActiveSession(datasetId)
    setActiveSection('overview')
    setActiveErrorMsg('')
    resetAllSections()
    try {
      const meta = await api(`/api/dataset-analyzer/sessions/${datasetId}`)
      setActiveStatus(meta.status)
      setActiveErrorMsg(meta.error_message || '')
      setSessions(prev => prev.map(s => (s.dataset_id === datasetId ? { ...s, ...meta } : s)))
    } catch {
      setActiveStatus('error')
      setActiveErrorMsg('Failed to load session status')
    }
  }, [])

  React.useEffect(() => {
    if (!activeSession) return
    if (activeStatus !== 'processing' && activeStatus !== 'uploading') return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const poll = async () => {
      if (cancelled) return
      try {
        const meta = await api(`/api/dataset-analyzer/sessions/${activeSession}`)
        if (cancelled) return
        setActiveStatus(meta.status)
        setActiveErrorMsg(meta.error_message || '')
        setSessions(prev => prev.map(s => (s.dataset_id === activeSession ? { ...s, ...meta } : s)))
        if (meta.status === 'processing' || meta.status === 'uploading') {
          timer = setTimeout(poll, 500)
        }
      } catch (e: any) {
        if (cancelled) return
        setActiveStatus('error')
        setActiveErrorMsg(e.message || 'Status check failed')
      }
    }
    timer = setTimeout(poll, 500)
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [activeSession, activeStatus])

  const handleUpload = async () => {
    if (!selectedFile) return
    setUploading(true)
    setUploadError('')
    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      const result = await api('/api/dataset-analyzer/sessions', { method: 'POST', body: formData })
      setSelectedFile(null)
      await loadSessions()
      if (result.dataset_id) {
        setActiveStatus(result.status || 'processing')
        loadSessionData(result.dataset_id)
      }
    } catch (e: any) {
      setUploadError(e.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (datasetId: string) => {
    setDeletingId(datasetId)
    try {
      await api(`/api/dataset-analyzer/sessions/${datasetId}`, { method: 'DELETE' })
      if (activeSession === datasetId) {
        setActiveSession(null)
        setActiveStatus(null)
        setActiveErrorMsg('')
        resetAllSections()
      }
      await loadSessions()
    } catch (e: any) {
      console.error('Delete failed:', e)
    } finally {
      setDeletingId(null)
    }
  }

  const handleAsk = async (question?: string) => {
    const q = (question ?? askQuestion).trim()
    if (!q || !activeSession) return
    setAskResult(prev => ({ ...prev, loading: true, error: '' }))
    try {
      const result = await api(`/api/dataset-analyzer/sessions/${activeSession}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      setAskResult({ loading: false, data: result, error: '' })
      setAskHistory(prev => [{ question: q, result }, ...prev].slice(0, 20))
      setAskQuestion('')
    } catch (e: any) {
      setAskResult({ loading: false, data: null, error: e.message || 'Query failed' })
    }
  }

  const chooseSuggested = (q: any) => {
    setAskResult({ loading: false, data: q, error: '' })
    setAskHistory(prev => [{ question: q.question, result: q }, ...prev].slice(0, 20))
  }

  const activeSessionMeta = sessions.find(s => s.dataset_id === activeSession)

  const sectionState = (id: SectionId): SectionState => sections[id] || { loading: false, data: null, error: '' }

  const renderSectionContent = () => {
    if (activeStatus === 'processing' || activeStatus === 'uploading') {
      return (
        <section className="ds-panel">
          <SectionHeader title="Preparing Dataset" subtitle="Profiling runs in the background" />
          <LoadingState label="dataset analysis" />
        </section>
      )
    }
    if (activeStatus === 'error') {
      return (
        <section className="ds-panel">
          <SectionHeader title="Dataset Error" />
          <ErrorState message={activeErrorMsg || 'Dataset processing failed'} />
        </section>
      )
    }
    if (activeStatus !== 'ready') {
      return (
        <section className="ds-panel">
          <SectionHeader title="Loading Status" />
          <LoadingState label="session status" />
        </section>
      )
    }
    const st = sectionState(activeSection)
    switch (activeSection) {
      case 'overview':
        return <DatasetOverview overview={st} />
      case 'kpis':
        return <DynamicKPIs kpis={st} />
      case 'analytics':
        return <AnalyticsSection analytics={st} />
      case 'trends':
        return <TrendsSection trends={st} />
      case 'domain':
        return <DomainSection domain={st} />
      case 'geospatial':
        return <GeospatialSection geospatial={st} />
      case 'routes':
        return <RoutesSection routes={st} />
      case 'anomalies':
        return <AnomaliesSection anomalies={st} />
      case 'ask':
        return (
          <AskSection
            queries={queries}
            askQuestion={askQuestion}
            setAskQuestion={setAskQuestion}
            handleAsk={handleAsk}

            askResult={askResult}
            askHistory={askHistory}
          />
        )
      case 'insights':
        return <InsightsSection insights={st} />
      case 'report':
        return <ReportSection report={st} />
    }
  }

  return (
    <div className="ds-workspace">
      {!activeSession && (
        <div className="ds-home">
          <div className="ds-home-badge">
            <span>◆</span>
            DATA INTELLIGENCE LAB
          </div>
          <h3>Understand Any Dataset.</h3>
          <p className="ds-home-desc">
            Upload a CSV, XLS, or XLSX dataset and let SupplySphere automatically
            discover its schema, capabilities, statistics, trends, anomalies,
            geospatial patterns, insights and reports.
          </p>

          <div className="ds-upload-area" style={{ justifyContent: 'center' }}>
            <input
              type="file"
              id="ds-file-input"
              accept=".csv,.xls,.xlsx"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) { setSelectedFile(f); setUploadError('') } }}
            />
            <label htmlFor="ds-file-input" className="ds-file-label">
              {selectedFile ? selectedFile.name : 'Choose CSV, XLS, or XLSX'}
            </label>
            <button className="ds-btn ds-btn-primary" onClick={handleUpload} disabled={uploading || !selectedFile}>
              {uploading ? 'Uploading...' : 'Upload Dataset'}
            </button>
            {selectedFile && <span className="ds-file-size">{formatFileSize(selectedFile.size)}</span>}
          </div>
          {uploadError && <div className="ds-upload-error">{uploadError}</div>}
          <div className="ds-home-note">
            Maximum file size 500 MB · Your data is processed locally · Sessions expire automatically
          </div>
        </div>
      )}

      {!activeSession && sessions.length > 0 && (
        <>
          <h2>Recent Datasets</h2>
          <div className="ds-sessions-grid">
            {sessions.map(s => (
              <div key={s.dataset_id} className="ds-session-card" onClick={() => loadSessionData(s.dataset_id)}>
                <div className="ds-session-card-header">
                  <span className="ds-session-name">{s.original_filename}</span>
                  <span className={`ds-status ds-status-${s.status}`}>{s.status}</span>
                </div>
                <div className="ds-session-meta">
                  <KVRow label="Format" value={s.file_format?.toUpperCase()} />
                  <KVRow label="Size" value={formatFileSize(s.file_size_bytes)} />
                  {s.row_count != null && <KVRow label="Rows" value={s.row_count.toLocaleString()} />}
                  {s.column_count != null && <KVRow label="Columns" value={s.column_count} />}
                  <KVRow label="Created" value={new Date(s.created_at).toLocaleString()} />
                </div>
                <button
                  className="ds-btn ds-btn-danger ds-btn-sm"
                  onClick={(e) => { e.stopPropagation(); handleDelete(s.dataset_id) }}
                  disabled={deletingId === s.dataset_id}
                >
                  {deletingId === s.dataset_id ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {activeSession && (
        <div className="ds-active-workspace">
          <div className="ds-session-bar">
            <button className="ds-btn ds-btn-ghost" onClick={() => { setActiveSession(null); setActiveStatus(null); setActiveErrorMsg(''); resetAllSections() }}>
              ← Sessions
            </button>
            {activeSessionMeta && (
              <div className="ds-session-bar-info">
                <strong>{activeSessionMeta.original_filename}</strong>
                <span className={`ds-status ds-status-${activeStatus || activeSessionMeta.status}`}>{activeStatus || activeSessionMeta.status}</span>
                {activeSessionMeta.row_count != null && <span>{activeSessionMeta.row_count.toLocaleString()} rows</span>}
                {activeSessionMeta.column_count != null && <span>{activeSessionMeta.column_count} columns</span>}
                <span>{formatFileSize(activeSessionMeta.file_size_bytes)}</span>
              </div>
            )}
            <button
              className="ds-btn ds-btn-danger ds-btn-sm"
              onClick={() => handleDelete(activeSession)}
              disabled={deletingId === activeSession}
            >
              {deletingId === activeSession ? 'Deleting...' : 'Delete Dataset'}
            </button>
          </div>

          <div className="ds-lab-layout">
            <nav className="ds-section-nav">
              {SECTION_NAV.map(item => (
                <button
                  key={item.id}
                  className={`ds-section-nav-item ${activeSection === item.id ? 'active' : ''}`}
                  onClick={() => setActiveSection(item.id)}
                  disabled={activeStatus !== 'ready'}
                >
                  <span className="ds-section-nav-dot" />
                  {item.label}
                </button>
              ))}
            </nav>

            <div className="ds-section-content">
              {renderSectionContent()}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function DatasetOverview({ overview }: { overview: SectionState }) {
  if (overview.loading && !overview.data) return <section className="ds-panel"><SectionHeader title="Dataset Overview" /><LoadingState label="overview" /></section>
  if (overview.error) return <section className="ds-panel"><SectionHeader title="Dataset Overview" /><ErrorState message={overview.error} /></section>
  if (!overview.data) return null
  const p = overview.data.profile || {}
  const cols: Record<string, any> = p.column_profiles || {}
  const colNames: string[] = p.column_names || []
  const caps: any[] = overview.data.capabilities?.capabilities || []

  return (
    <section className="ds-panel">
      <SectionHeader title="Dataset Overview" subtitle={`Profiled ${p.profiled_at ? new Date(p.profiled_at).toLocaleString() : ''}`} />
      <div className="ds-kpi-grid">
        <div className="ds-kpi-card"><span className="ds-kpi-label">Rows</span><span className="ds-kpi-value">{p.row_count?.toLocaleString()}</span></div>
        <div className="ds-kpi-card"><span className="ds-kpi-label">Columns</span><span className="ds-kpi-value">{p.column_count}</span></div>
        <div className="ds-kpi-card"><span className="ds-kpi-label">Duplicates</span><span className="ds-kpi-value">{p.duplicate_row_count?.toLocaleString()}</span></div>
        <div className="ds-kpi-card"><span className="ds-kpi-label">Numeric</span><span className="ds-kpi-value">{p.numeric_columns?.length || 0}</span></div>
        <div className="ds-kpi-card"><span className="ds-kpi-label">Categorical</span><span className="ds-kpi-value">{p.categorical_columns?.length || 0}</span></div>
        <div className="ds-kpi-card"><span className="ds-kpi-label">DateTime</span><span className="ds-kpi-value">{p.datetime_columns?.length || 0}</span></div>
      </div>

      {colNames.length > 0 && (
        <div className="ds-sub-section">
          <h4>Column Details</h4>
          <div className="ds-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Column</th>
                  <th>Type</th>
                  <th>Unique</th>
                  <th>Null %</th>
                  <th>Duplicates</th>
                  <th>Candidates</th>
                </tr>
              </thead>
              <tbody>
                {colNames.map(name => {
                  const c = cols[name]
                  if (!c) return null
                  const candidates = []
                  if (c.is_id_candidate) candidates.push('ID')
                  if (c.is_geographic_candidate) candidates.push('Geo')
                  if (c.is_measure_candidate) candidates.push('Measure')
                  return (
                    <tr key={name}>
                      <td><strong>{name}</strong></td>
                      <td>{c.inferred_type}</td>
                      <td>{c.unique_count}</td>
                      <td>{c.null_percentage != null ? `${c.null_percentage.toFixed(1)}%` : '—'}</td>
                      <td>{c.duplicate_count}</td>
                      <td>{candidates.length > 0 ? candidates.join(', ') : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {caps.length > 0 && (
        <div className="ds-sub-section">
          <h4>Detected Capabilities</h4>
          <div className="ds-capabilities">
            {caps.map((c: any) => <CapabilityBadge key={c.name} name={c.name} status={c.status} detected_fields={c.detected_fields || []} />)}
          </div>
        </div>
      )}

      {p.limitations && p.limitations.length > 0 && (
        <div className="ds-limitations">
          <h4>Limitations</h4>
          <ul>{p.limitations.map((l: string, i: number) => <li key={i}>{l}</li>)}</ul>
        </div>
      )}
    </section>
  )
}

function DynamicKPIs({ kpis }: { kpis: SectionState }) {
  if (kpis.loading && !kpis.data) return <section className="ds-panel"><SectionHeader title="Key Performance Indicators" /><LoadingState label="KPIs" /></section>
  if (kpis.error) return <section className="ds-panel"><SectionHeader title="Key Performance Indicators" /><ErrorState message={kpis.error} /></section>
  if (!kpis.data) return null
  const items: any[] = kpis.data.kpis || []
  const available = items.filter((k: any) => k.available)

  if (available.length === 0) return <section className="ds-panel"><SectionHeader title="Key Performance Indicators" /><EmptyState message="No KPIs available for this dataset" /></section>

  return (
    <section className="ds-panel">
      <SectionHeader title="Key Performance Indicators" />
      <div className="ds-kpi-grid">
        {available.map((k: any) => (
          <div key={k.name} className="ds-kpi-card">
            <span className="ds-kpi-label">{k.name.replace(/_/g, ' ')}</span>
            <span className="ds-kpi-value">{typeof k.value === 'number' ? k.value.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(k.value)}</span>
            <span className="ds-kpi-source">{k.source_columns?.join(', ')}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function AnalyticsSection({ analytics }: { analytics: SectionState }) {
  if (analytics.loading && !analytics.data) return <section className="ds-panel"><SectionHeader title="Analytics" /><LoadingState label="analytics" /></section>
  if (analytics.error) return <section className="ds-panel"><SectionHeader title="Analytics" /><ErrorState message={analytics.error} /></section>
  if (!analytics.data) return null
  const results: any[] = analytics.data.results || []
  const available = results.filter((r: any) => r.available)

  if (available.length === 0) return <section className="ds-panel"><SectionHeader title="Analytics" /><EmptyState message="No analytics available" /></section>

  return (
    <section className="ds-panel">
      <SectionHeader title="Analytics" />
      {available.map((r: any, i: number) => (
        <div key={i} className="ds-analytics-result">
          <h4>{r.name}</h4>
          <div className="ds-analytics-meta">
            <span className="ds-tag">{r.result_type}</span>
            <span>Columns: {r.source_columns?.join(', ')}</span>
          </div>
          {r.result_type === 'table' && Array.isArray(r.data) && (
            <MiniTable columns={r.data.length > 0 ? Object.keys(r.data[0]) : []} rows={r.data} />
          )}
          {r.result_type === 'key_value' && typeof r.data === 'object' && (
            <div className="ds-kv-grid">
              {Object.entries(r.data).map(([k, v]) => <KVRow key={k} label={k} value={typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(v)} />)}
            </div>
          )}
          {r.result_type === 'list' && Array.isArray(r.data) && (
            <MiniTable columns={r.data.length > 0 ? Object.keys(r.data[0]) : []} rows={r.data} />
          )}
          {r.limitations && r.limitations.length > 0 && (
            <div className="ds-limitations"><ul>{r.limitations.map((l: string, j: number) => <li key={j}>{l}</li>)}</ul></div>
          )}
        </div>
      ))}
    </section>
  )
}

function TrendsSection({ trends }: { trends: SectionState }) {
  if (trends.loading && !trends.data) return <section className="ds-panel"><SectionHeader title="Trends" /><LoadingState label="trends" /></section>
  if (trends.error) return <section className="ds-panel"><SectionHeader title="Trends" /><ErrorState message={trends.error} /></section>
  if (!trends.data) return null
  const items: any[] = trends.data.trends || []
  const available = items.filter((t: any) => t.available)

  if (available.length === 0) return <section className="ds-panel"><SectionHeader title="Trends" /><EmptyState message="No trend data available for this dataset" /></section>

  return (
    <section className="ds-panel">
      <SectionHeader title="Trends" />
      {available.map((t: any, i: number) => (
        <div key={i} className="ds-trend-result">
          <div className="ds-trend-header">
            <h4>{t.name}</h4>
            {t.trend_direction && <span className="ds-tag">{t.trend_direction}</span>}
          </div>
          <div className="ds-trend-meta">
            <span>Date: {t.date_column}</span>
            <span>Measure: {t.measure_column}</span>
            {t.aggregation_period && <span>Period: {t.aggregation_period}</span>}
          </div>
          {t.trend_summary && typeof t.trend_summary === 'object' && (
            <div className="ds-kv-grid">
              {Object.entries(t.trend_summary).map(([k, v]) => (
                <KVRow key={k} label={k} value={typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(v)} />
              ))}
            </div>
          )}
          {Array.isArray(t.data) && t.data.length > 0 && (
            <MiniTable columns={Object.keys(t.data[0])} rows={t.data} maxRows={30} />
          )}
        </div>
      ))}
    </section>
  )
}

function DomainSection({ domain }: { domain: SectionState }) {
  if (domain.loading && !domain.data) return <section className="ds-panel"><SectionHeader title="Domain Analysis" /><LoadingState label="domain analysis" /></section>
  if (domain.error) return <section className="ds-panel"><SectionHeader title="Domain Analysis" /><ErrorState message={domain.error} /></section>
  if (!domain.data) return null
  const results: any[] = domain.data.results || []
  const available = results.filter((r: any) => r.available)

  if (available.length === 0) return <section className="ds-panel"><SectionHeader title="Domain Analysis" /><EmptyState message="No domain-specific analysis available" /></section>

  return (
    <section className="ds-panel">
      <SectionHeader title="Domain Analysis" />
      {available.map((r: any, i: number) => (
        <div key={i} className="ds-domain-result">
          <div className="ds-domain-header">
            <h4>{r.domain?.replace(/_/g, ' ')}</h4>
          </div>
          <p className="ds-domain-desc">{r.description}</p>
          <div className="ds-domain-meta">
            <span>Columns: {r.source_columns?.join(', ')}</span>
            <span>Basis: {r.calculation_basis}</span>
          </div>
          {r.metrics && typeof r.metrics === 'object' && Object.keys(r.metrics).length > 0 && (
            <div className="ds-metrics-grid">
              {Object.entries(r.metrics).map(([k, v]) => {
                if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
                  return (
                    <div key={k} className="ds-metric-group">
                      <h5>{k.replace(/_/g, ' ')}</h5>
                      <div className="ds-kv-grid">
                        {Object.entries(v as Record<string, any>).map(([mk, mv]) => (
                          <KVRow key={mk} label={mk} value={typeof mv === 'number' ? mv.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(mv)} />
                        ))}
                      </div>
                    </div>
                  )
                }
                return <KVRow key={k} label={k} value={typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(v)} />
              })}
            </div>
          )}
          {r.limitations && r.limitations.length > 0 && (
            <div className="ds-limitations"><ul>{r.limitations.map((l: string, j: number) => <li key={j}>{l}</li>)}</ul></div>
          )}
        </div>
      ))}
    </section>
  )
}

function GeospatialPreview({ bbox }: { bbox: any }) {
  if (!bbox) return null
  const minLat = bbox.min_lat ?? bbox.min_latitude
  const maxLat = bbox.max_lat ?? bbox.max_latitude
  const minLon = bbox.min_lon ?? bbox.min_longitude ?? bbox.min_lng
  const maxLon = bbox.max_lon ?? bbox.max_longitude ?? bbox.max_lng
  if (minLat == null || maxLat == null || minLon == null || maxLon == null) return null

  const latSpan = Math.max(maxLat - minLat, 0.0001)
  const lonSpan = Math.max(maxLon - minLon, 0.0001)
  const pad = 0.18
  const x0 = 8, y0 = 8, w = 352, h = 220
  const X = (lon: number) => x0 + ((lon - minLon) / lonSpan) * w
  const Y = (lat: number) => y0 + (h - ((lat - minLat) / latSpan) * h)

  const tx = (lon: number) => x0 + ((lon - minLon) / lonSpan) * w
  const ty = (lat: number) => y0 + (h - ((lat - minLat) / latSpan) * h)
  void X; void Y

  const gridLonMax = Math.min(8, Math.max(2, Math.round(lonSpan / (10 ** Math.floor(Math.log10(lonSpan)) * 0.5))))
  const gridLatMax = Math.min(8, Math.max(2, Math.round(latSpan / (10 ** Math.floor(Math.log10(latSpan)) * 0.5))))

  return (
    <div className="ds-map-preview">
      <svg viewBox="0 0 392 252" role="img" aria-label="Geographic bounding box preview" style={{ width: '100%', height: 'auto', display: 'block' }}>
        <defs>
          <linearGradient id="ds-map-bg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0f172a" />
            <stop offset="100%" stopColor="#0b1020" />
          </linearGradient>
          <linearGradient id="ds-map-accent" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#38bdf8" />
            <stop offset="100%" stopColor="#818cf8" />
          </linearGradient>
        </defs>
        <rect x={x0} y={y0} width={w} height={h} rx={8} fill="url(#ds-map-bg)" stroke="rgba(148,163,184,0.25)" />

        {Array.from({ length: gridLonMax - 1 }).map((_, i) => {
          const lon = minLon + (lonSpan * (i + 1)) / gridLonMax
          const x = tx(lon)
          return <line key={`v${i}`} x1={x} y1={y0 + 1} x2={x} y2={y0 + h - 1} stroke="rgba(148,163,184,0.1)" strokeDasharray="4 5" />
        })}
        {Array.from({ length: gridLatMax - 1 }).map((_, i) => {
          const lat = minLat + (latSpan * (i + 1)) / gridLatMax
          const y = ty(lat)
          return <line key={`h${i}`} x1={x0 + 1} y1={y} x2={x0 + w - 1} y2={y} stroke="rgba(148,163,184,0.1)" strokeDasharray="4 5" />
        })}

        <rect x={x0} y={y0} width={w} height={h} rx={8} fill="none" stroke="url(#ds-map-accent)" strokeWidth={1.5} />
        <polygon points={`${tx(minLon)},${ty(maxLat)} ${tx(maxLon)},${ty(minLat)}`} fill="rgba(56,189,248,0.08)" />

        <circle cx={tx(minLon)} cy={ty(minLat)} r={4.5} fill="#38bdf8" />
        <circle cx={tx(maxLon)} cy={ty(minLat)} r={4.5} fill="#818cf8" />
        <circle cx={tx(minLon)} cy={ty(maxLat)} r={4.5} fill="#38bdf8" />
        <circle cx={tx(maxLon)} cy={ty(maxLat)} r={4.5} fill="#818cf8" />

        <text x={tx(minLon)} y={ty(minLat) + 5} textAnchor="end" dy="16" fontSize="9" fill="#94a3b8">SW</text>
        <text x={tx(maxLon)} y={ty(minLat) - 5} textAnchor="start" dy="-4" fontSize="9" fill="#94a3b8">SE</text>
        <text x={tx(minLon)} y={ty(maxLat) - 5} textAnchor="start" dy="-6" fontSize="9" fill="#94a3b8">NW</text>
        <text x={tx(maxLon)} y={ty(maxLat) + 5} textAnchor="end" dy="18" fontSize="9" fill="#94a3b8">NE</text>
      </svg>
      <div className="ds-map-preview-caption">
        <span>Coverage: {lonSpan.toFixed(4)}° lon × {latSpan.toFixed(4)}° lat</span>
        <span>{bbox.record_count != null ? `${bbox.record_count.toLocaleString()} records` : ''}</span>
      </div>
    </div>
  )
}

function GeospatialSection({ geospatial }: { geospatial: SectionState }) {
  if (geospatial.loading && !geospatial.data) return <section className="ds-panel"><SectionHeader title="Geospatial Analysis" /><LoadingState label="geospatial data" /></section>
  if (geospatial.error) return <section className="ds-panel"><SectionHeader title="Geospatial Analysis" /><ErrorState message={geospatial.error} /></section>
  if (!geospatial.data) return null
  const geo = geospatial.data.geospatial
  if (!geo) return <section className="ds-panel"><SectionHeader title="Geospatial Analysis" /><EmptyState message="No geospatial data available" /></section>

  const od = geospatial.data.origin_destination

  return (
    <section className="ds-panel">
      <SectionHeader title="Geospatial Analysis" />
      <div className="ds-kpi-grid">
        <div className="ds-kpi-card"><span className="ds-kpi-label">Valid Coordinates</span><span className="ds-kpi-value">{geo.valid_coordinate_count?.toLocaleString()}</span></div>
        <div className="ds-kpi-card"><span className="ds-kpi-label">Invalid Coordinates</span><span className="ds-kpi-value">{geo.invalid_coordinate_count?.toLocaleString()}</span></div>
        <div className="ds-kpi-card"><span className="ds-kpi-label">Total Records</span><span className="ds-kpi-value">{geo.total_records?.toLocaleString()}</span></div>
        <div className="ds-kpi-card"><span className="ds-kpi-label">Valid %</span><span className="ds-kpi-value">{geo.valid_percentage?.toFixed(1)}%</span></div>
      </div>

      {geo.bounding_box && (
        <div className="ds-sub-section">
          <h4>Bounding Box</h4>
          <div className="ds-kv-grid">
            <KVRow label="Min Latitude" value={geo.bounding_box.min_lat?.toFixed(4)} />
            <KVRow label="Max Latitude" value={geo.bounding_box.max_lat?.toFixed(4)} />
            <KVRow label="Min Longitude" value={geo.bounding_box.min_lon?.toFixed(4)} />
            <KVRow label="Max Longitude" value={geo.bounding_box.max_lon?.toFixed(4)} />
          </div>

          <GeospatialPreview bbox={geo.bounding_box} />
        </div>
      )}

      {geo.coordinate_distribution && typeof geo.coordinate_distribution === 'object' && (
        <div className="ds-sub-section">
          <h4>Coordinate Distribution</h4>
          <div className="ds-kv-grid">
            {Object.entries(geo.coordinate_distribution).map(([k, v]) => (
              <KVRow key={k} label={k} value={typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(v)} />
            ))}
          </div>
        </div>
      )}

      {od && (
        <div className="ds-sub-section">
          <h4>Origin/Destination Summary</h4>
          <div className="ds-kpi-grid">
            <div className="ds-kpi-card"><span className="ds-kpi-label">Unique Origins</span><span className="ds-kpi-value">{od.unique_origins}</span></div>
            <div className="ds-kpi-card"><span className="ds-kpi-label">Unique Destinations</span><span className="ds-kpi-value">{od.unique_destinations}</span></div>
            <div className="ds-kpi-card"><span className="ds-kpi-label">Unique Routes</span><span className="ds-kpi-value">{od.unique_routes}</span></div>
          </div>
        </div>
      )}

      {geo.source_columns && (
        <div className="ds-source-info">Source columns: {geo.source_columns.join(', ')}</div>
      )}
      {geo.limitations && geo.limitations.length > 0 && (
        <div className="ds-limitations"><ul>{geo.limitations.map((l: string, i: number) => <li key={i}>{l}</li>)}</ul></div>
      )}
    </section>
  )
}

function RoutesSection({ routes }: { routes: SectionState }) {
  if (routes.loading && !routes.data) return <section className="ds-panel"><SectionHeader title="Route Analysis" /><LoadingState label="route data" /></section>
  if (routes.error) return <section className="ds-panel"><SectionHeader title="Route Analysis" /><ErrorState message={routes.error} /></section>
  if (!routes.data) return null
  const r = routes.data.routes
  if (!r) return <section className="ds-panel"><SectionHeader title="Route Analysis" /><EmptyState message="No route data available" /></section>

  return (
    <section className="ds-panel">
      <SectionHeader title="Route Analysis" />
      <div className="ds-kpi-grid">
        <div className="ds-kpi-card"><span className="ds-kpi-label">Unique Origins</span><span className="ds-kpi-value">{r.unique_origins}</span></div>
        <div className="ds-kpi-card"><span className="ds-kpi-label">Unique Destinations</span><span className="ds-kpi-value">{r.unique_destinations}</span></div>
        <div className="ds-kpi-card"><span className="ds-kpi-label">Unique Routes</span><span className="ds-kpi-value">{r.unique_routes}</span></div>
        {r.route_volume != null && <div className="ds-kpi-card"><span className="ds-kpi-label">Route Volume</span><span className="ds-kpi-value">{r.route_volume.toLocaleString()}</span></div>}
      </div>

      {r.top_routes && r.top_routes.length > 0 && (
        <div className="ds-sub-section">
          <h4>Top Routes</h4>
          <MiniTable columns={Object.keys(r.top_routes[0])} rows={r.top_routes} />
        </div>
      )}

      {r.route_frequency && Object.keys(r.route_frequency).length > 0 && (
        <div className="ds-sub-section">
          <h4>Route Frequency</h4>
          <div className="ds-kv-grid">
            {Object.entries(r.route_frequency).slice(0, 20).map(([k, v]) => (
              <KVRow key={k} label={k} value={String(v)} />
            ))}
          </div>
        </div>
      )}

      {r.source_columns && <div className="ds-source-info">Source columns: {r.source_columns.join(', ')}</div>}
      {r.limitations && r.limitations.length > 0 && (
        <div className="ds-limitations"><ul>{r.limitations.map((l: string, i: number) => <li key={i}>{l}</li>)}</ul></div>
      )}
    </section>
  )
}

function AnomaliesSection({ anomalies }: { anomalies: SectionState }) {
  if (anomalies.loading && !anomalies.data) return <section className="ds-panel"><SectionHeader title="Anomaly Detection" /><LoadingState label="anomalies" /></section>
  if (anomalies.error) return <section className="ds-panel"><SectionHeader title="Anomaly Detection" /><ErrorState message={anomalies.error} /></section>
  if (!anomalies.data) return null
  const items: any[] = anomalies.data.anomalies || []
  const available = items.filter((a: any) => a.affected_rows > 0)

  if (available.length === 0) return <section className="ds-panel"><SectionHeader title="Anomaly Detection" /><EmptyState message="No anomalies detected" /></section>

  return (
    <section className="ds-panel">
      <SectionHeader title="Anomaly Detection" />
      {available.map((a: any, i: number) => (
        <div key={i} className="ds-anomaly-result">
          <div className="ds-anomaly-header">
            <h4>Method: {a.method}</h4>
            <span className="ds-tag">{a.affected_rows} affected rows</span>
          </div>
          <div className="ds-kv-grid">
            <KVRow label="Threshold" value={a.threshold} />
            <KVRow label="Total Rows" value={a.total_rows?.toLocaleString()} />
            <KVRow label="Source Columns" value={a.source_columns?.join(', ')} />
            <KVRow label="Basis" value={a.calculation_basis} />
          </div>
          {a.limitations && a.limitations.length > 0 && (
            <div className="ds-limitations"><ul>{a.limitations.map((l: string, j: number) => <li key={j}>{l}</li>)}</ul></div>
          )}
        </div>
      ))}
    </section>
  )
}

function AskSection({ askQuestion, setAskQuestion, handleAsk, askResult, askHistory, queries }: {
  askQuestion: string
  setAskQuestion: (v: string) => void
  handleAsk: () => void
  askResult: SectionState
  askHistory: Array<{ question: string; result: any }>
  queries: SectionState
}) {
  const suggestions: any[] = queries.data?.queries || []
  const shown = suggestions.slice(0, 4)
  return (
    <section className="ds-panel">
      <SectionHeader title="Ask Your Dataset" subtitle="Ask natural language questions about your data" />
      <div className="ds-ask-input-row">
        <input
          className="ds-ask-input"
          type="text"
          placeholder="e.g. What is the average sales? Which product has the highest revenue?"
          value={askQuestion}
          onChange={e => setAskQuestion(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleAsk() }}
        />
        <button className="ds-btn ds-btn-primary" onClick={handleAsk} disabled={askResult.loading || !askQuestion.trim()}>
          {askResult.loading ? 'Analyzing...' : 'Ask'}
        </button>
      </div>

      {askResult.loading && <LoadingState label="answer" />}
      {askResult.error && <ErrorState message={askResult.error} />}

      {askResult.data && (
        <div className="ds-ask-answer">
          <div className="ds-ask-answer-main">
            <h4>Answer</h4>
            <div className="ds-ask-answer-value">
              {typeof askResult.data.answer === 'object' ? JSON.stringify(askResult.data.answer, null, 2) : String(askResult.data.answer)}
            </div>
          </div>
          <div className="ds-ask-answer-meta">
            <KVRow label="Result Type" value={askResult.data.result_type} />
            <KVRow label="Source Columns" value={askResult.data.source_columns?.join(', ')} />
            <KVRow label="Calculation" value={askResult.data.calculation_basis} />
            <KVRow label="Supported" value={askResult.data.supported ? 'Yes' : 'No'} />
            {askResult.data.reason && <KVRow label="Reason" value={askResult.data.reason} />}
          </div>
          {askResult.data.limitations && askResult.data.limitations.length > 0 && (
            <div className="ds-limitations"><ul>{askResult.data.limitations.map((l: string, i: number) => <li key={i}>{l}</li>)}</ul></div>
          )}
        </div>
      )}

      {askHistory.length > 0 && (
        <div className="ds-ask-history">
          <h4>Recent Questions</h4>
          {askHistory.map((h, i) => (
            <div key={i} className="ds-ask-history-item">
              <div className="ds-ask-history-q">Q: {h.question}</div>
              <div className="ds-ask-history-a">A: {typeof h.result?.answer === 'object' ? JSON.stringify(h.result.answer) : String(h.result?.answer ?? '')}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function InsightsSection({ insights }: { insights: SectionState }) {
  if (insights.loading && !insights.data) return <section className="ds-panel"><SectionHeader title="Insights" /><LoadingState label="insights" /></section>
  if (insights.error) return <section className="ds-panel"><SectionHeader title="Insights" /><ErrorState message={insights.error} /></section>
  if (!insights.data) return null
  const items: any[] = insights.data.insights || []

  if (items.length === 0) return <section className="ds-panel"><SectionHeader title="Insights" /><EmptyState message="No insights generated" /></section>

  return (
    <section className="ds-panel">
      <SectionHeader title="Insights" subtitle={`Generated ${insights.data.computed_at ? new Date(insights.data.computed_at).toLocaleString() : ''}`} />
      <div className="ds-insights-grid">
        {items.map((ins: any, i: number) => (
          <div key={i} className="ds-insight-card">
            <div className="ds-insight-header">
              <strong>{ins.name}</strong>
            </div>
            <div className="ds-insight-value">
              {typeof ins.value === 'object' ? (
                <div className="ds-kv-grid">
                  {Object.entries(ins.value).map(([k, v]) => (
                    <KVRow key={k} label={k} value={typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(v)} />
                  ))}
                </div>
              ) : (
                <span>{String(ins.value)}</span>
              )}
            </div>
            <div className="ds-insight-meta">
              <span>Columns: {ins.source_columns?.join(', ')}</span>
              <span>Basis: {ins.calculation_basis}</span>
            </div>
            {ins.limitations && ins.limitations.length > 0 && (
              <div className="ds-limitations"><ul>{ins.limitations.map((l: string, j: number) => <li key={j}>{l}</li>)}</ul></div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

function ReportSection({ report }: { report: SectionState }) {
  if (report.loading && !report.data) return <section className="ds-panel"><SectionHeader title="Comprehensive Report" /><LoadingState label="report" /></section>
  if (report.error) return <section className="ds-panel"><SectionHeader title="Comprehensive Report" /><ErrorState message={report.error} /></section>
  if (!report.data) return null
  const r = report.data

  return (
    <section className="ds-panel">
      <SectionHeader title="Comprehensive Report" subtitle={`Generated ${r.computed_at ? new Date(r.computed_at).toLocaleString() : ''}`} />

      {r.dataset_summary && (
        <div className="ds-report-section">
          <h4>Dataset Summary</h4>
          <div className="ds-kv-grid">
            {Object.entries(r.dataset_summary).map(([k, v]) => (
              <KVRow key={k} label={k.replace(/_/g, ' ')} value={typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(v)} />
            ))}
          </div>
        </div>
      )}

      {r.kpis && r.kpis.kpis && (
        <div className="ds-report-section">
          <h4>KPIs</h4>
          <div className="ds-kpi-grid">
            {r.kpis.kpis.filter((k: any) => k.available).map((k: any) => (
              <div key={k.name} className="ds-kpi-card">
                <span className="ds-kpi-label">{k.name.replace(/_/g, ' ')}</span>
                <span className="ds-kpi-value">{typeof k.value === 'number' ? k.value.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(k.value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {r.insights && r.insights.insights && r.insights.insights.length > 0 && (
        <div className="ds-report-section">
          <h4>Insights Summary</h4>
          {r.insights.insights.map((ins: any, i: number) => (
            <div key={i} className="ds-report-insight">
              <strong>{ins.name}</strong>: {typeof ins.value === 'object' ? JSON.stringify(ins.value) : String(ins.value)}
            </div>
          ))}
        </div>
      )}

      {r.unavailable && Object.keys(r.unavailable).length > 0 && (
        <div className="ds-report-section">
          <h4>Unavailable Sections</h4>
          <div className="ds-kv-grid">
            {Object.entries(r.unavailable).map(([k, v]) => (
              <KVRow key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
