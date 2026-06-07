import { useState, useRef, useEffect } from 'react'
import { ingestSource, uploadPdf } from '../api'
import './IngestForm.css'

// Detect if running on HuggingFace Spaces
const IS_HF = typeof window !== 'undefined' && window.location.hostname.includes('hf.space')

function IngestForm({ onComplete, isIngesting, setIsIngesting, reloadError, onClearReloadError }) {
  const [source, setSource] = useState('')
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  // When a sidebar reload fails, pre-fill the source URL so user can retry easily
  useEffect(() => {
    if (reloadError?.source) {
      setSource(reloadError.source)
      setError(reloadError.message)
    }
  }, [reloadError])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!source.trim()) return

    setIsIngesting(true)
    setError(null)
    if (onClearReloadError) onClearReloadError()

    try {
      const data = await ingestSource(source.trim())
      onComplete(data)
      setSource('')
    } catch (err) {
      setError(err.message)
      setIsIngesting(false)
    }
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    if (!file.name.endsWith('.pdf')) {
      setError('Only PDF files are supported')
      return
    }

    setIsIngesting(true)
    setError(null)

    try {
      const data = await uploadPdf(file)
      onComplete(data)
    } catch (err) {
      setError(err.message)
      setIsIngesting(false)
    }

    fileInputRef.current.value = ''
  }

  return (
    <div className="ingest-form">
      <div className="ingest-welcome">
        <div className="ingest-logo">◈</div>
        <h2>Ask anything about <span>any content</span></h2>
        <p>Paste a YouTube URL, webpage link, or upload a PDF — then chat with it</p>
      </div>

      <div className="ingest-input-area">
        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="Paste a YouTube URL, webpage, or article..."
              disabled={isIngesting}
            />
            <button type="submit" disabled={isIngesting || !source.trim()}>
              {isIngesting ? 'Analyzing…' : 'Analyze →'}
            </button>
            <button
              type="button"
              className="upload-btn"
              onClick={() => fileInputRef.current.click()}
              disabled={isIngesting}
            >
              📄 PDF
            </button>
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />
          </div>
        </form>

        {isIngesting && (
          <div className="ingest-progress">
            <div className="ingest-progress-bar">
              <div className="ingest-progress-fill" />
            </div>
            <span className="ingest-progress-text">Processing content…</span>
          </div>
        )}

        {!isIngesting && (
          <div className="ingest-hints">
            <span className="hint-chip">▶ YouTube videos</span>
            <span className="hint-chip">📰 Blog posts</span>
            <span className="hint-chip">📚 Documentation</span>
            <span className="hint-chip">📄 PDF files</span>
          </div>
        )}

        {error && (
          <p className="error">
            ⚠ {error}
            {reloadError && ' — click Analyze to retry'}
          </p>
        )}

        {/* HuggingFace platform note — only shown on hf.space */}
        {IS_HF && (
          <div className="hf-note">
            <span className="hf-note-icon">ℹ️</span>
            <div>
              <strong>Note:</strong> YouTube URLs are not supported on this demo.
              HuggingFace Spaces blocks outbound connections to YouTube for security reasons.
              Use a <strong>webpage URL</strong> or <strong>PDF</strong> instead.
              YouTube works fully on the self-hosted version.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default IngestForm
