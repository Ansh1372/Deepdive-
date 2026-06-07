import { useState, useEffect } from 'react'
import './Dashboard.css'

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8001"

function Dashboard({ onClose }) {
  const [metrics, setMetrics] = useState(null)
  const [error, setError] = useState(null)

  const fetchMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/metrics`)
      if (!res.ok) throw new Error('Failed to fetch metrics')
      const data = await res.json()
      setMetrics(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    fetchMetrics()
    const interval = setInterval(fetchMetrics, 10000) // refresh every 10s
    return () => clearInterval(interval)
  }, [])

  if (error) {
    return (
      <div className="dashboard">
        <div className="dashboard-header">
          <h2>Metrics</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        <p className="dashboard-error">Could not load metrics: {error}</p>
      </div>
    )
  }

  if (!metrics) {
    return (
      <div className="dashboard">
        <div className="dashboard-header">
          <h2>Metrics</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        <p className="dashboard-loading">Loading...</p>
      </div>
    )
  }

  const pipelineSteps = metrics.pipeline_avg_times || {}

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>Metrics Dashboard</h2>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-value">{metrics.total_requests}</div>
          <div className="metric-label">Total Requests</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{metrics.total_chats}</div>
          <div className="metric-label">Chats</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{metrics.total_ingests}</div>
          <div className="metric-label">Ingestions</div>
        </div>
        <div className="metric-card error">
          <div className="metric-value">{metrics.total_errors}</div>
          <div className="metric-label">Errors</div>
        </div>
      </div>

      <div className="metrics-grid two-col">
        <div className="metric-card highlight">
          <div className="metric-value">{metrics.avg_response_time_s}s</div>
          <div className="metric-label">Avg Response Time</div>
        </div>
        <div className="metric-card highlight">
          <div className="metric-value">{metrics.p95_response_time_s}s</div>
          <div className="metric-label">P95 Response Time</div>
        </div>
      </div>

      {Object.keys(pipelineSteps).length > 0 && (
        <div className="pipeline-section">
          <h3>Pipeline Breakdown</h3>
          <div className="pipeline-bars">
            {Object.entries(pipelineSteps).map(([step, time]) => (
              <div className="pipeline-row" key={step}>
                <span className="pipeline-name">{step}</span>
                <div className="pipeline-bar-bg">
                  <div
                    className="pipeline-bar-fill"
                    style={{ width: `${Math.min((time / metrics.avg_response_time_s) * 100, 100)}%` }}
                  />
                </div>
                <span className="pipeline-time">{time}s</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard
