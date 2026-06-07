import { useState } from 'react'
import './SourcePanel.css'

function SourcePanel({ sources }) {
  const [expanded, setExpanded] = useState(false)

  if (!sources || sources.length === 0) return null

  return (
    <div className="source-panel">
      <button
        className="source-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        📎 {sources.length} source{sources.length > 1 ? 's' : ''} used
        <span className="toggle-icon">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="source-list">
          {sources.map((src, i) => (
            <div key={i} className="source-item">
              <div className="source-header">
                <span className="source-badge">Chunk {src.chunk_index + 1}</span>
                <span className="source-url">{src.source}</span>
              </div>
              <p className="source-content">{src.content}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default SourcePanel
