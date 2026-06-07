import { useState } from 'react'
import './PipelinePanel.css'

/**
 * Badge confidence is based on the ACTUAL answer outcome, not the raw
 * cross-encoder score. The reranker score is a technical retrieval metric
 * that is low for vague/open-ended queries even when the answer is good.
 *
 * Logic:
 *  - Web search was triggered + found content → MEDIUM (answer supplemented from web)
 *  - Web search was triggered + nothing useful → LOW (couldn't find a good answer)
 *  - Answer came entirely from ingested document (sufficiency passed) → HIGH
 */
function getOutcomeConfidence(pipeline) {
  if (pipeline.web_augmented) {
    // Web search was used — answer is partially from web, not purely from document
    return { label: 'Medium', className: 'confidence-medium' }
  }
  // Check if sufficiency check explicitly failed (web search attempted but found nothing)
  const sufficiencyStep = pipeline.steps?.find(s => s.name === 'Context Sufficiency Check')
  if (sufficiencyStep && sufficiencyStep.detail?.includes('Insufficient')) {
    return { label: 'Low', className: 'confidence-low' }
  }
  // Sufficiency passed, answered from document
  return { label: 'High', className: 'confidence-high' }
}

function normalizeConfidence(score) {
  // Map raw reranker score (-5 to 10) to 0-100% for the internal bar
  const normalized = Math.max(0, Math.min(100, ((score + 5) / 15) * 100))
  return normalized
}

function PipelinePanel({ pipeline }) {
  const [expanded, setExpanded] = useState(false)

  if (!pipeline) return null

  const rawScore = pipeline.confidence          // reranker score — for the internal bar
  const outcomeInfo = getOutcomeConfidence(pipeline)  // outcome badge — what user sees

  return (
    <div className="pipeline-panel">
      <button
        className="pipeline-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="pipeline-toggle-left">
          ⚡ Pipeline: {pipeline.total_time}s ({pipeline.steps.length} steps)
          <span className={`confidence-badge ${outcomeInfo.className}`}>
            {outcomeInfo.label} confidence
          </span>
          {pipeline.web_augmented && (
            <span className="web-badge">🌐 Web augmented</span>
          )}
        </span>
        <span className="toggle-icon">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="pipeline-details">
          {rawScore !== undefined && (
            <div className="confidence-bar-container">
              <span className="label">Retrieval Score:</span>
              <div className="confidence-bar-bg">
                <div
                  className={`confidence-bar-fill ${outcomeInfo.className}`}
                  style={{ width: `${normalizeConfidence(rawScore)}%` }}
                />
              </div>
              <span className={`confidence-score ${outcomeInfo.className}`}>
                {rawScore.toFixed(1)}
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
