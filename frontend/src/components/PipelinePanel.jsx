import { useState } from 'react'
import './PipelinePanel.css'

function getConfidenceLevel(score) {
  // Raw CrossEncoder scores: typically -10 to +10
  // Threshold is 5.0 — below that triggers web search
  if (score >= 7) return { label: 'High', className: 'confidence-high' }
  if (score >= 5) return { label: 'Medium', className: 'confidence-medium' }
  return { label: 'Low', className: 'confidence-low' }
}

function normalizeConfidence(score) {
  // Map raw score (-5 to 10) to 0-100% for the bar
  const normalized = Math.max(0, Math.min(100, ((score + 5) / 15) * 100))
  return normalized
}

function PipelinePanel({ pipeline }) {
  const [expanded, setExpanded] = useState(false)

  if (!pipeline) return null

  const confidence = pipeline.confidence
  const confidenceInfo = confidence !== undefined ? getConfidenceLevel(confidence) : null

  return (
    <div className="pipeline-panel">
      <button
        className="pipeline-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="pipeline-toggle-left">
          ⚡ Pipeline: {pipeline.total_time}s ({pipeline.steps.length} steps)
          {confidenceInfo && (
            <span className={`confidence-badge ${confidenceInfo.className}`}>
              {confidenceInfo.label} confidence
            </span>
          )}
          {pipeline.web_augmented && (
            <span className="web-badge">🌐 Web augmented</span>
          )}
        </span>
        <span className="toggle-icon">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="pipeline-details">
          {confidenceInfo && (
            <div className="confidence-bar-container">
              <span className="label">Retrieval Confidence:</span>
              <div className="confidence-bar-bg">
                <div
                  className={`confidence-bar-fill ${confidenceInfo.className}`}
                  style={{ width: `${normalizeConfidence(confidence)}%` }}
                />
              </div>
              <span className={`confidence-score ${confidenceInfo.className}`}>
                {confidence.toFixed(1)}
              </span>
            </div>
          )}
          <div className="pipeline-query">
            <span className="label">Original:</span> {pipeline.original_query}
          </div>
          <div className="pipeline-query">
            <span className="label">Rewritten:</span> {pipeline.rewritten_query}
          </div>
          {pipeline.variations && pipeline.variations.length > 0 && (
            <div className="pipeline-variations">
              <span className="label">Variations:</span>
              {pipeline.variations.map((v, i) => (
                <div key={i} className="variation">→ {v}</div>
              ))}
            </div>
          )}
          <div className="pipeline-steps">
            {pipeline.steps.map((step, i) => (
              <div key={i} className={`pipeline-step ${step.name.includes('Web Search') ? 'step-highlight' : ''}`}>
                <span className="step-name">{step.name}</span>
                <span className="step-detail">{step.detail || step.result || ''}</span>
                <span className="step-time">{step.time}s</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default PipelinePanel
