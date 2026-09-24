import React from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import LandingPage from './LandingPage'
import OlistControlTower from './OlistControlTower'
import DatasetAnalyzer from './DatasetAnalyzer'

type View = 'landing' | 'control-tower' | 'dataset-analyzer'

function App() {
  const [view, setView] = React.useState<View>('landing')

  React.useEffect(() => {
    const handlePopState = () => {
      const hash = window.location.hash.replace('#', '') || 'landing'
      if (hash === 'control-tower' || hash === 'dataset-analyzer' || hash === 'landing') {
        setView(hash as View)
      }
    }
    handlePopState()
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const navigate = (newView: View) => {
    setView(newView)
    window.location.hash = newView === 'landing' ? '' : newView
  }

  if (view === 'control-tower') {
    return <OlistControlTower onBack={() => navigate('landing')} />
  }

  if (view === 'dataset-analyzer') {
    return (
      <div className="app">
        <aside className="ds-standalone-aside">
          <button className="back-btn" onClick={() => navigate('landing')}>
            ← Home
          </button>
          <div className="brand">
            Supply<span>Sphere</span>
            <small>DATASET ANALYZER</small>
          </div>
        </aside>
        <main>
          <DatasetAnalyzer />
        </main>
      </div>
    )
  }

  return (
    <LandingPage
      onOpenControlTower={() => navigate('control-tower')}
      onOpenDatasetAnalyzer={() => navigate('dataset-analyzer')}
    />
  )
}

createRoot(document.getElementById('root')!).render(<App />)
