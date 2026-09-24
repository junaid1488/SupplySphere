import React from 'react'

/* ────────── DATA: capabilities (10 per design brief) ────────── */
const capabilities = [
  { title: 'Demand', desc: 'Forecast demand patterns across products, regions, and time horizons.', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6', color: '#3b82f6', size: 'large' as const },
  { title: 'Inventory', desc: 'Monitor stock levels, identify stockout risks, and warehouse utilization.', icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4', color: '#06b6d4', size: 'large' as const },
  { title: 'Suppliers', desc: 'Evaluate supplier performance, lead times, and sourcing decisions.', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z', color: '#8b5cf6', size: 'small' as const },
  { title: 'Logistics', desc: 'Track routes, shipments, delivery performance, and carrier efficiency.', icon: 'M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10m10 0H3m10 0a2 2 0 012 2v2a2 2 0 01-2 2H9m4 0a2 2 0 002-2v-2a2 2 0 00-2-2', color: '#f59e0b', size: 'small' as const },
  { title: 'Geospatial', desc: 'Visualize operations across warehouses, routes, and global locations.', icon: 'M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064', color: '#3b82f6', size: 'medium' as const },
  { title: 'Optimization', desc: 'Evaluate network decisions for cost, service level, and operational efficiency.', icon: 'M13 10V3L4 14h7v7l9-11h-7z', color: '#10b981', size: 'medium' as const },
  { title: 'Analytics', desc: 'Compute statistics, distributions, and performance indicators per column.', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z', color: '#8b5cf6', size: 'small' as const },
  { title: 'Dataset Intelligence', desc: 'Upload any dataset and discover structure, analytics, anomalies, and insights.', icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4', color: '#ec4899', size: 'medium' as const },
  { title: 'Insights', desc: 'Surface critical findings, anomalies, and recommendations automatically.', icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z', color: '#3b82f6', size: 'small' as const },
  { title: 'Reports', desc: 'Generate executive reports that consolidate risk and operational metrics.', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', color: '#f43f5e', size: 'small' as const },
]

const pipelineSteps = [
  { label: 'DATA', sub: 'Ingest' },
  { label: 'UNDERSTAND', sub: 'Profile' },
  { label: 'ANALYZE', sub: 'Compute' },
  { label: 'OPTIMIZE', sub: 'Solve' },
  { label: 'DECIDE', sub: 'Act' },
]

/* ────────── HERO: Supply Chain Network SVG ────────── */
function HeroNetwork() {
  return (
    <svg className="lp-hero-network" viewBox="0 0 800 600" preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id="hRouteGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0" />
          <stop offset="25%" stopColor="#3b82f6" stopOpacity="0.5" />
          <stop offset="75%" stopColor="#06b6d4" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#06b6d4" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="hRouteGradV" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0" />
          <stop offset="40%" stopColor="#3b82f6" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#06b6d4" stopOpacity="0" />
        </linearGradient>
        <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
        </radialGradient>
        <filter id="hGlow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Geographic grid lines */}
      <g stroke="rgba(56,189,248,0.04)" strokeWidth="0.5">
        {[100, 150, 200, 250, 300, 350, 400, 450, 500].map(y => (
          <line key={`h${y}`} x1="0" y1={y} x2="800" y2={y} />
        ))}
        {[100, 180, 260, 340, 420, 500, 580, 660].map(x => (
          <line key={`v${x}`} x1={x} y1="0" x2={x} y2="600" />
        ))}
      </g>

      {/* Latitude/longitude labels */}
      <g fill="rgba(56,189,248,0.08)" fontSize="7" fontFamily="Inter, monospace" fontWeight="500">
        <text x="8" y="104">40°N</text>
        <text x="8" y="204">20°N</text>
        <text x="8" y="304">0°</text>
        <text x="8" y="404">20°S</text>
        <text x="8" y="504">40°S</text>
        <text x="100" y="590">60°W</text>
        <text x="260" y="590">30°W</text>
        <text x="420" y="590">0°</text>
        <text x="580" y="590">30°E</text>
        <text x="660" y="590">60°E</text>
      </g>

      {/* Continent outlines - more visible, refined */}
      <g stroke="rgba(56,189,248,0.1)" strokeWidth="0.8" fill="rgba(56,189,248,0.015)">
        {/* North America */}
        <path d="M80 80 Q110 60 150 65 L190 80 Q210 95 220 120 L215 160 Q210 180 190 195 L160 205 Q140 215 120 208 L100 195 Q80 175 72 150 L70 110 Q72 90 80 80Z" />
        <path d="M120 205 Q145 225 165 235 L180 245 Q188 255 180 265 L165 275" fill="none" />
        {/* South America */}
        <path d="M160 300 Q180 290 190 310 L200 350 Q210 390 200 430 L185 455 Q175 465 165 455 L155 425 Q148 390 150 360 L152 330 Q155 310 160 300Z" />
        {/* Europe */}
        <path d="M350 70 Q370 60 395 65 L420 78 Q435 88 442 105 L435 125 Q428 135 415 140 L395 145 Q378 143 368 135 L358 120 Q348 105 348 85 L350 70Z" />
        {/* Africa */}
        <path d="M370 180 Q390 170 415 175 L440 190 Q455 208 462 235 L465 275 Q460 310 445 335 L430 352 Q415 360 400 352 L385 335 Q372 310 368 280 L365 240 Q367 205 370 180Z" />
        {/* Asia */}
        <path d="M455 55 Q490 45 535 48 L590 60 Q625 70 650 90 L665 115 Q672 140 665 165 L650 188 Q635 205 610 212 L580 218 Q555 222 530 215 L505 200 Q488 188 480 170 L472 145 Q462 120 460 95 L458 70 Q456 58 455 55Z" />
        <path d="M610 212 Q635 228 652 248 L660 275 Q664 295 652 305" fill="none" />
        {/* Australia */}
        <path d="M600 340 Q625 330 655 335 L680 348 Q692 358 688 375 L675 388 Q658 398 638 394 L620 385 Q608 375 602 358 L600 340Z" />
      </g>

      {/* Animated shipping routes */}
      <g filter="url(#hGlow)">
        <path d="M175 140 Q270 85 395 100" stroke="url(#hRouteGrad)" strokeWidth="1" fill="none" className="lp-hero-route" style={{ animationDelay: '0s' }} />
        <path d="M395 100 Q500 60 620 75" stroke="url(#hRouteGrad)" strokeWidth="1" fill="none" className="lp-hero-route" style={{ animationDelay: '1.2s' }} />
        <path d="M175 140 Q250 240 390 260" stroke="url(#hRouteGrad)" strokeWidth="0.8" fill="none" className="lp-hero-route" style={{ animationDelay: '2.4s' }} />
        <path d="M395 100 Q440 170 415 260" stroke="url(#hRouteGrad)" strokeWidth="0.8" fill="none" className="lp-hero-route" style={{ animationDelay: '1.8s' }} />
        <path d="M620 75 Q645 200 660 350" stroke="url(#hRouteGrad)" strokeWidth="0.7" fill="none" className="lp-hero-route" style={{ animationDelay: '3.5s' }} />
        <path d="M390 260 Q500 320 610 350" stroke="url(#hRouteGrad)" strokeWidth="0.7" fill="none" className="lp-hero-route" style={{ animationDelay: '4s' }} />
        {/* Vertical connector routes */}
        <path d="M270 200 L270 340" stroke="url(#hRouteGradV)" strokeWidth="0.6" fill="none" className="lp-hero-route" style={{ animationDelay: '2s' }} />
        <path d="M500 160 L500 310" stroke="url(#hRouteGradV)" strokeWidth="0.6" fill="none" className="lp-hero-route" style={{ animationDelay: '3s' }} />
      </g>

      {/* Route particles */}
      <circle r="2" fill="#38bdf8" className="lp-hero-particle" style={{ offsetPath: "path('M175 140 Q270 85 395 100')", animationDelay: '0s' }} />
      <circle r="1.8" fill="#06b6d4" className="lp-hero-particle" style={{ offsetPath: "path('M395 100 Q500 60 620 75')", animationDelay: '1.5s' }} />
      <circle r="1.6" fill="#38bdf8" className="lp-hero-particle" style={{ offsetPath: "path('M175 140 Q250 240 390 260')", animationDelay: '3s' }} />
      <circle r="1.5" fill="#06b6d4" className="lp-hero-particle" style={{ offsetPath: "path('M620 75 Q645 200 660 350')", animationDelay: '4s' }} />

      {/* Warehouse/destination nodes */}
      {[
        { x: 175, y: 140, label: 'São Paulo', size: 5, type: 'primary' },
        { x: 395, y: 100, label: 'London', size: 4.5, type: 'primary' },
        { x: 620, y: 75, label: 'Tokyo', size: 4.5, type: 'primary' },
        { x: 415, y: 260, label: 'Lagos', size: 3.5, type: 'secondary' },
        { x: 500, y: 200, label: 'Dubai', size: 3.5, type: 'secondary' },
        { x: 610, y: 350, label: 'Sydney', size: 3.5, type: 'secondary' },
        { x: 110, y: 105, label: 'Los Angeles', size: 4, type: 'primary' },
        { x: 270, y: 120, label: 'New York', size: 4, type: 'primary' },
        { x: 580, y: 140, label: 'Mumbai', size: 3.5, type: 'secondary' },
        { x: 160, y: 320, label: 'Buenos Aires', size: 3, type: 'tertiary' },
        { x: 660, y: 250, label: 'Singapore', size: 3, type: 'tertiary' },
      ].map((n, i) => (
        <g key={i}>
          {n.type === 'primary' && (
            <circle cx={n.x} cy={n.y} r={n.size + 10} fill="url(#nodeGlow)" className="lp-hero-node-glow" style={{ animationDelay: `${i * 0.5}s` }} />
          )}
          <circle cx={n.x} cy={n.y} r={n.size + 3} fill={n.type === 'primary' ? 'rgba(59,130,246,0.1)' : 'rgba(6,182,212,0.08)'} />
          <circle cx={n.x} cy={n.y} r={n.size} fill="#080d16" stroke={n.type === 'primary' ? '#3b82f6' : '#06b6d4'} strokeWidth="1.2" />
          <circle cx={n.x} cy={n.y} r={n.size * 0.35} fill={n.type === 'primary' ? '#3b82f6' : '#06b6d4'} />
          <text x={n.x} y={n.y + n.size + 12} textAnchor="middle" fill="rgba(148,163,184,0.25)" fontSize="7" fontWeight="500" fontFamily="Inter, sans-serif">{n.label}</text>
        </g>
      ))}
    </svg>
  )
}

/* ────────── CONTROL TOWER PREVIEW ────────── */
function ControlTowerPreview() {
  return (
    <div className="lp-ct-preview">
      {/* Sidebar */}
      <div className="lp-ct-sidebar">
        <div className="lp-ct-sidebar-logo">
          <span className="lp-ct-sidebar-diamond">◆</span>
          <span>Control Tower</span>
        </div>
        {['Dashboard', 'Demand Forecast', 'Inventory', 'Warehouses', 'Suppliers', 'Logistics', 'Geospatial', 'Optimization', 'AI Insights', 'Reports', 'Settings'].map((item, i) => (
          <div key={item} className={`lp-ct-nav ${i === 0 ? 'lp-ct-nav--active' : ''}`}>
            <span className="lp-ct-nav-dot" />
            {item}
          </div>
        ))}
      </div>
      {/* Main content area */}
      <div className="lp-ct-main">
        <div className="lp-ct-topbar">
          <span className="lp-ct-topbar-title">Operations Overview</span>
          <div className="lp-ct-topbar-actions">
            <span className="lp-ct-topbar-badge">Live</span>
            <span className="lp-ct-topbar-filter">Last 30 days ▾</span>
          </div>
        </div>
        {/* Mini map + chart row */}
        <div className="lp-ct-content-row">
          <div className="lp-ct-mini-map">
            <svg viewBox="0 0 180 120" className="lp-ct-map-svg">
              <g stroke="rgba(59,130,246,0.08)" strokeWidth="0.5">
                {[20,40,60,80,100].map(y => <line key={y} x1="0" y1={y} x2="180" y2={y} />)}
                {[30,60,90,120,150].map(x => <line key={x} x1={x} y1="0" x2={x} y2="120" />)}
              </g>
              <path d="M30 40 Q70 20 110 35 Q140 45 160 30" stroke="rgba(59,130,246,0.25)" strokeWidth="0.8" fill="none" className="lp-ct-route" />
              <path d="M30 40 Q50 70 80 80 Q100 85 120 75" stroke="rgba(6,182,212,0.2)" strokeWidth="0.6" fill="none" className="lp-ct-route" style={{ animationDelay: '1s' }} />
              {[[30,40],[80,30],[110,35],[140,50],[80,80],[160,30]].map(([x,y],i) => (
                <g key={i}>
                  <circle cx={x} cy={y} r="3" fill="#0a0f18" stroke="#3b82f6" strokeWidth="0.8" />
                  <circle cx={x} cy={y} r="1.2" fill="#3b82f6" />
                </g>
              ))}
            </svg>
            <span className="lp-ct-map-label">Geospatial Operations</span>
          </div>
          <div className="lp-ct-chart-area">
            <div className="lp-ct-chart-header">
              <span>Demand Trend</span>
              <span className="lp-ct-chart-period">30d</span>
            </div>
            <svg viewBox="0 0 200 60" className="lp-ct-chart-svg">
              <defs>
                <linearGradient id="ctChartFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.12" />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
                </linearGradient>
              </defs>
              <polyline points="0,50 15,46 30,38 45,42 60,30 75,34 90,24 105,28 120,20 135,22 150,16 165,18 180,12 200,8" fill="none" stroke="#3b82f6" strokeWidth="1.2" />
              <polygon points="0,50 15,46 30,38 45,42 60,30 75,34 90,24 105,28 120,20 135,22 150,16 165,18 180,12 200,8 200,60 0,60" fill="url(#ctChartFill)" />
            </svg>
            <div className="lp-ct-chart-labels">
              <span>Jan</span><span>Feb</span><span>Mar</span><span>Apr</span><span>May</span><span>Jun</span>
            </div>
          </div>
        </div>
        {/* Feature tags */}
        <div className="lp-ct-features-row">
          {['Demand Forecast', 'Inventory Risk', 'Supplier Analytics', 'Route Optimization', 'AI Insights'].map(f => (
            <span key={f} className="lp-ct-feature-tag">{f}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ────────── DATASET ANALYZER PREVIEW ────────── */
function DatasetPreview() {
  return (
    <div className="lp-ds-preview">
      {/* Sidebar */}
      <div className="lp-ct-sidebar lp-ds-sidebar">
        <div className="lp-ct-sidebar-logo lp-ds-logo">
          <span className="lp-ct-sidebar-diamond" style={{ color: '#06b6d4' }}>◆</span>
          <span>Dataset Analyzer</span>
        </div>
        {['Overview', 'KPIs', 'Analytics', 'Trends', 'Geospatial', 'Anomalies', 'Ask', 'Insights', 'Report'].map((item, i) => (
          <div key={item} className={`lp-ct-nav ${i === 0 ? 'lp-ct-nav--active lp-ct-nav--teal' : ''}`}>
            <span className="lp-ct-nav-dot" />
            {item}
          </div>
        ))}
      </div>
      {/* Main content - flow visualization */}
      <div className="lp-ds-main">
        <div className="lp-ds-flow">
          {[
            { icon: '⬆', label: 'Upload Dataset', desc: 'CSV, XLS, XLSX' },
            { icon: '⬡', label: 'Schema Discovery', desc: 'Columns, types, domains' },
            { icon: '📊', label: 'Analytics', desc: 'Statistics & distributions' },
            { icon: '📈', label: 'Trend Detection', desc: 'Time-series patterns' },
            { icon: '⚡', label: 'Anomaly Alerts', desc: 'Outlier identification' },
            { icon: '💡', label: 'Insights', desc: 'Auto-generated findings' },
            { icon: '📋', label: 'Report', desc: 'Comprehensive summary' },
          ].map((step, i) => (
            <React.Fragment key={step.label}>
              <div className="lp-ds-step">
                <div className="lp-ds-step-icon">{step.icon}</div>
                <div className="lp-ds-step-label">{step.label}</div>
                <div className="lp-ds-step-desc">{step.desc}</div>
              </div>
              {i < 6 && <div className="lp-ds-arrow">→</div>}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ────────── MAIN LANDING PAGE ────────── */
export default function LandingPage({ onOpenControlTower, onOpenDatasetAnalyzer }: {
  onOpenControlTower: () => void
  onOpenDatasetAnalyzer: () => void
}) {
  const [scrolled, setScrolled] = React.useState(false)
  React.useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const flowRef = React.useRef<HTMLDivElement>(null)
  React.useEffect(() => {
    const el = flowRef.current
    if (!el) return
    const steps = Array.from(el.querySelectorAll<HTMLElement>('.lp-flow-step'))
    if (!('IntersectionObserver' in window)) {
      steps.forEach(s => s.classList.add('lp-flow-step--visible'))
      return
    }
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('lp-flow-step--visible')
          observer.unobserve(entry.target)
        }
      })
    }, { threshold: 0.3 })
    steps.forEach(s => observer.observe(s))
    return () => observer.disconnect()
  }, [])

  return (
    <div className="lp">
      {/* ── NAVBAR ── */}
      <nav className={`lp-nav ${scrolled ? 'lp-nav--scrolled' : ''}`}>
        <div className="lp-nav-inner">
          <a href="#" className="lp-nav-brand" onClick={e => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>
            <span className="lp-nav-logo">◆</span>
            SupplySphere
          </a>
          <div className="lp-nav-links">
            <a href="#workspaces">Platform</a>
            <a href="#ct-showcase">Control Tower</a>
            <a href="#ds-showcase">Dataset Analyzer</a>
            <a href="#capabilities">Capabilities</a>
          </div>
          <button className="lp-nav-cta" onClick={onOpenControlTower}>Explore Platform</button>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section className="lp-hero">
        <div className="lp-hero-bg">
          <HeroNetwork />
          <div className="lp-hero-gradient-overlay" />
        </div>

        <div className="lp-hero-layout">
          <div className="lp-hero-left">
            <div className="lp-hero-badge">
              <span className="lp-hero-badge-dot" />
              SUPPLY CHAIN INTELLIGENCE
            </div>

            <h1 className="lp-hero-title">
              See Your Supply Chain.<br />
              Understand Every Move.
            </h1>

            <p className="lp-hero-desc">
              SupplySphere brings operational supply-chain intelligence
              and dataset-driven analysis into one platform.
            </p>

            <div className="lp-hero-ctas">
              <button className="lp-btn lp-btn--primary" onClick={onOpenControlTower}>
                Open Control Tower
                <svg width="15" height="15" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </button>
              <button className="lp-btn lp-btn--outline" onClick={onOpenDatasetAnalyzer}>
                Analyze Your Dataset
                <svg width="15" height="15" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── TWO INTELLIGENCE WORKSPACES ── */}
      <section className="lp-section lp-section--workspaces" id="workspaces">
        <div className="lp-section-inner">
          <div className="lp-section-header">
            <div className="lp-section-tag">PLATFORM</div>
            <h2 className="lp-section-title">Two Intelligence Systems. One Supply Chain Platform.</h2>
            <p className="lp-section-desc">
              Operational supply-chain control and flexible dataset intelligence — unified in one platform.
            </p>
          </div>

          {/* Control Tower Showcase */}
          <div className="lp-showcase" id="ct-showcase">
            <div className="lp-showcase-text">
              <div className="lp-showcase-badge lp-showcase-badge--blue">OPERATIONAL INTELLIGENCE</div>
              <h3 className="lp-showcase-name">Olist Control Tower</h3>
              <p className="lp-showcase-desc">
                Monitor demand, inventory, suppliers, logistics, geospatial operations,
                optimization, insights and reports through a unified operational workspace.
              </p>
              <button className="lp-btn lp-btn--primary lp-showcase-cta" onClick={onOpenControlTower}>
                Open Control Tower
                <svg width="15" height="15" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </button>
            </div>
            <div className="lp-showcase-preview">
              <ControlTowerPreview />
            </div>
          </div>

          {/* Dataset Analyzer Showcase */}
          <div className="lp-showcase lp-showcase--reverse" id="ds-showcase">
            <div className="lp-showcase-text">
              <div className="lp-showcase-badge lp-showcase-badge--teal">DATA INTELLIGENCE</div>
              <h3 className="lp-showcase-name">Dataset Analyzer</h3>
              <p className="lp-showcase-desc">
                Upload a dataset and automatically discover its schema, capabilities,
                statistics, trends, anomalies, geospatial patterns, insights and reports.
              </p>
              <button className="lp-btn lp-btn--teal lp-showcase-cta" onClick={onOpenDatasetAnalyzer}>
                Analyze a Dataset
                <svg width="15" height="15" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </button>
            </div>
            <div className="lp-showcase-preview">
              <DatasetPreview />
            </div>
          </div>
        </div>
      </section>

      {/* ── INTELLIGENCE FLOW ── */}
      <section className="lp-section lp-section--flow" id="flow">
        <div className="lp-section-inner">
          <div className="lp-section-header">
            <div className="lp-section-tag">WORKFLOW</div>
            <h2 className="lp-section-title">From Data to Operational Intelligence</h2>
            <p className="lp-section-desc">
              A structured intelligence pipeline that transforms raw data into operational decisions.
            </p>
          </div>

          <div className="lp-flow" ref={flowRef}>
            {/* Connecting line */}
            <div className="lp-flow-line" />
            {pipelineSteps.map((step, i) => (
              <div key={step.label} className="lp-flow-step">
                <div className="lp-flow-node">
                  <div className="lp-flow-number">{String(i + 1).padStart(2, '0')}</div>
                </div>
                <div className="lp-flow-content">
                  <div className="lp-flow-label">{step.label}</div>
                  <div className="lp-flow-sub">{step.sub}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CAPABILITIES ── */}
      <section className="lp-section lp-section--caps" id="capabilities">
        <div className="lp-section-inner">
          <div className="lp-section-header">
            <div className="lp-section-tag">CAPABILITIES</div>
            <h2 className="lp-section-title">Intelligence Across the Network</h2>
            <p className="lp-section-desc">
              Every module is designed to answer the critical questions operations teams face daily.
            </p>
          </div>

          <div className="lp-caps-layout">
            {/* Left column - 2 large */}
            <div className="lp-caps-col lp-caps-col--left">
              {capabilities.filter(c => c.size === 'large').map(c => (
                <div key={c.title} className="lp-cap-card lp-cap-card--large">
                  <div className="lp-cap-icon-wrap" style={{ background: `${c.color}0d`, borderColor: `${c.color}20` }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={c.color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d={c.icon} />
                    </svg>
                  </div>
                  <h3 className="lp-cap-title">{c.title}</h3>
                  <p className="lp-cap-desc">{c.desc}</p>
                </div>
              ))}
            </div>

            {/* Center column - 2 medium with network visualization */}
            <div className="lp-caps-col lp-caps-col--center">
              <div className="lp-caps-network">
                <svg viewBox="0 0 240 280" className="lp-caps-network-svg">
                  <defs>
                    <radialGradient id="capNodeGlow" cx="50%" cy="50%" r="50%">
                      <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.2" />
                      <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
                    </radialGradient>
                  </defs>
                  <g stroke="rgba(59,130,246,0.12)" strokeWidth="0.6" fill="none">
                    <line x1="120" y1="40" x2="60" y2="100" />
                    <line x1="120" y1="40" x2="180" y2="100" />
                    <line x1="60" y1="100" x2="40" y2="170" />
                    <line x1="180" y1="100" x2="200" y2="170" />
                    <line x1="60" y1="100" x2="120" y2="170" />
                    <line x1="180" y1="100" x2="120" y2="170" />
                    <line x1="40" y1="170" x2="80" y2="240" />
                    <line x1="120" y1="170" x2="120" y2="240" />
                    <line x1="200" y1="170" x2="160" y2="240" />
                  </g>
                  {[[120,40],[60,100],[180,100],[40,170],[120,170],[200,170],[80,240],[120,240],[160,240]].map(([x,y],i) => (
                    <g key={i}>
                      <circle cx={x} cy={y} r="8" fill="url(#capNodeGlow)" />
                      <circle cx={x} cy={y} r="4" fill="#0a0f18" stroke="#3b82f6" strokeWidth="0.8" />
                      <circle cx={x} cy={y} r="1.5" fill="#3b82f6" />
                    </g>
                  ))}
                </svg>
              </div>
              {capabilities.filter(c => c.size === 'medium').map(c => (
                <div key={c.title} className="lp-cap-card lp-cap-card--medium">
                  <div className="lp-cap-icon-wrap" style={{ background: `${c.color}0d`, borderColor: `${c.color}20` }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={c.color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d={c.icon} />
                    </svg>
                  </div>
                  <h3 className="lp-cap-title">{c.title}</h3>
                  <p className="lp-cap-desc">{c.desc}</p>
                </div>
              ))}
            </div>

            {/* Right column - 4 small */}
            <div className="lp-caps-col lp-caps-col--right">
              {capabilities.filter(c => c.size === 'small').map(c => (
                <div key={c.title} className="lp-cap-card lp-cap-card--small">
                  <div className="lp-cap-icon-wrap" style={{ background: `${c.color}0d`, borderColor: `${c.color}20` }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={c.color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d={c.icon} />
                    </svg>
                  </div>
                  <div className="lp-cap-text">
                    <h3 className="lp-cap-title">{c.title}</h3>
                    <p className="lp-cap-desc">{c.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ── */}
      <section className="lp-section lp-section--cta" id="cta">
        <div className="lp-cta-bg">
          <svg className="lp-cta-network" viewBox="0 0 800 200" preserveAspectRatio="xMidYMid slice">
            <g stroke="rgba(59,130,246,0.06)" strokeWidth="0.5">
              {[40,80,120,160].map(y => <line key={y} x1="0" y1={y} x2="800" y2={y} />)}
              {[100,200,300,400,500,600,700].map(x => <line key={x} x1={x} y1="0" x2={x} y2="200" />)}
            </g>
            <g stroke="rgba(59,130,246,0.1)" strokeWidth="0.6" fill="none">
              <path d="M0 100 Q200 60 400 100 Q600 140 800 100" />
              <path d="M0 120 Q200 80 400 120 Q600 160 800 120" />
            </g>
            {[[100,80],[250,60],[400,100],[550,80],[700,60],[200,120],[400,120],[600,120]].map(([x,y],i) => (
              <g key={i}>
                <circle cx={x} cy={y} r="3" fill="#0a0f18" stroke="rgba(59,130,246,0.2)" strokeWidth="0.6" />
                <circle cx={x} cy={y} r="1" fill="rgba(59,130,246,0.3)" />
              </g>
            ))}
          </svg>
        </div>
        <div className="lp-section-inner lp-cta-inner">
          <h2 className="lp-cta-title">Choose Your Intelligence Workspace.</h2>
          <div className="lp-cta-buttons">
            <button className="lp-btn lp-btn--primary" onClick={onOpenControlTower}>
              Open Control Tower
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </button>
            <button className="lp-btn lp-btn--teal" onClick={onOpenDatasetAnalyzer}>
              Analyze Your Dataset
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </button>
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <div className="lp-footer-brand">
            <span className="lp-nav-logo">◆</span>
            SupplySphere
          </div>
          <p className="lp-footer-tagline">Enterprise Supply Chain Intelligence</p>
          <div className="lp-footer-links">
            <a href="#workspaces">Platform</a>
            <a href="#ct-showcase">Control Tower</a>
            <a href="#ds-showcase">Dataset Analyzer</a>
            <a href="#capabilities">Capabilities</a>
          </div>
          <div className="lp-cta-footer">
            <button className="lp-footer-cta" onClick={onOpenControlTower}>Explore Platform</button>
          </div>
        </div>
      </footer>
    </div>
  )
}
