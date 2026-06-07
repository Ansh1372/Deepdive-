import { useState, useEffect } from 'react'
import ChatWindow from './components/ChatWindow'
import IngestForm from './components/IngestForm'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import { ingestSource } from './api'
import './App.css'

const HISTORY_KEY = 'deepdive_history'
const MAX_HISTORY = 5

function getSourceType(source) {
  if (source.includes('youtube.com') || source.includes('youtu.be')) return 'YouTube'
  if (source.endsWith('.pdf')) return 'PDF'
  if (source.startsWith('http')) return 'Webpage'
  return 'Document'
}

function getLabel(source) {
  if (source.includes('youtube.com') || source.includes('youtu.be')) {
    return 'YouTube Video'
  }
  if (source.endsWith('.pdf')) {
    return source.split('/').pop().replace('.pdf', '')
  }
  try {
    const url = new URL(source)
    let host = url.hostname.replace('www.', '')
    let path = url.pathname.replace(/\/$/, '').split('/').pop()
    if (path && path.length > 2) {
      return path.replace(/[-_]/g, ' ').slice(0, 35)
    }
    return host
  } catch {
    return source.slice(0, 35)
  }
}

function App() {
  const [sessionId, setSessionId] = useState(null)
  const [isIngesting, setIsIngesting] = useState(false)
  const [ingestInfo, setIngestInfo] = useState(null)
  const [history, setHistory] = useState([])
  const [showDashboard, setShowDashboard] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [reloadError, setReloadError] = useState(null) // {message, source} when sidebar reload fails

  // Fix mobile viewport height (100vh issue on mobile browsers)
  useEffect(() => {
    const setVH = () => {
      document.documentElement.style.setProperty('--vh', `${window.innerHeight * 0.01}px`)
    }
    setVH()
    window.addEventListener('resize', setVH)
    return () => window.removeEventListener('resize', setVH)
  }, [])

  useEffect(() => {
    const saved = localStorage.getItem(HISTORY_KEY)
    if (saved) {
      try { setHistory(JSON.parse(saved)) } catch {}
    }
    // Do NOT auto-restore last session on page load — the backend may have
    // restarted and the session may not be in memory. The user must click
    // the sidebar item which now triggers a proper /ingest reload.
    localStorage.removeItem('deepdive_active')
  }, [])

  const saveHistory = (newHistory) => {
    setHistory(newHistory)
    localStorage.setItem(HISTORY_KEY, JSON.stringify(newHistory))
  }

  const handleIngestComplete = (data) => {
    setSessionId(data.session_id)
    setIngestInfo(data)
    setIsIngesting(false)
    setReloadError(null) // clear any reload error
    localStorage.setItem('deepdive_active', JSON.stringify(data))

    const source = data.message
      .replace('Successfully ingested ', '')
      .replace('Using cached data for ', '')
      .replace('Loaded cached data for ', '')
      .replace('Successfully uploaded ', '')
    const entry = {
      session_id: data.session_id,
      source,                          // ← stored so sidebar can re-ingest
      label: getLabel(source),
      source_type: getSourceType(source),
      timestamp: Date.now(),
    }

    const updated = [entry, ...history.filter(h => h.session_id !== data.session_id)].slice(0, MAX_HISTORY)
    saveHistory(updated)
    setSidebarOpen(false)
  }

  const handleSelectHistory = async (item) => {
    if (item.source) {
      setIsIngesting(true)
      try {
        const data = await ingestSource(item.source)
        setSessionId(data.session_id)
        setIngestInfo({ ...data, cached: true })
        localStorage.setItem('deepdive_active', JSON.stringify({ ...data, cached: true }))
        setSidebarOpen(false)
      } catch (err) {
        // Reload failed (backend starting up, URL gone, etc.)
        // Stay on ingest form — do NOT open chat with a broken session
        setIsIngesting(false)
        setSessionId(null)
        setIngestInfo(null)
        localStorage.removeItem('deepdive_active')
        // Pre-fill the ingest form with the source URL so user can retry with one click
        setReloadError({ message: err.message, source: item.source })
        setSidebarOpen(false)
      } finally {
        setIsIngesting(false)
      }
    } else {
      // Old history entry without source — can't reload, go to ingest form
      setSessionId(null)
      setIngestInfo(null)
      localStorage.removeItem('deepdive_active')
      setSidebarOpen(false)
    }
  }

  const handleDeleteHistory = (sid) => {
    const updated = history.filter(h => h.session_id !== sid)
    saveHistory(updated)
  }

  const handleNewSession = () => {
    setSessionId(null)
    setIngestInfo(null)
    localStorage.removeItem('deepdive_active')
  }

  return (
    <div className="app-layout">
      {/* Mobile overlay */}
      <div
        className={`sidebar-overlay ${sidebarOpen ? 'visible' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      <Sidebar
        history={history}
        activeSession={sessionId}
        onSelect={handleSelectHistory}
        onDelete={handleDeleteHistory}
        onNewSession={handleNewSession}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        isLoading={isIngesting}
      />

      <div className="app">
        <header className="app-header">
          <button
            className="mobile-menu-btn"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
          >
            ☰
          </button>
          <h1>Deepdive</h1>
          <p>AI-Powered Content Q&A</p>
          <button className="metrics-toggle" onClick={() => setShowDashboard(!showDashboard)}>
            {showDashboard ? '✕ Close' : '📊 Metrics'}
          </button>
        </header>

        <main className="app-main">
          {showDashboard && (
            <Dashboard onClose={() => setShowDashboard(false)} />
          )}

          {!sessionId && (
            <IngestForm
              onComplete={handleIngestComplete}
              isIngesting={isIngesting}
              setIsIngesting={setIsIngesting}
              reloadError={reloadError}
              onClearReloadError={() => setReloadError(null)}
            />
          )}

          {sessionId && (
            <ChatWindow
              sessionId={sessionId}
              isReady={!!ingestInfo}
              isCached={ingestInfo?.cached}
              onNewSession={handleNewSession}
            />
          )}
        </main>
      </div>
    </div>
  )
}

export default App
