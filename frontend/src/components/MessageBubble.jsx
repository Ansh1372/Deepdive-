import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import './MessageBubble.css'

function MessageBubble({ role, content, isLoading }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = content
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className={`message ${role} fade-in`}>
      <div className="message-label">
        <span className="label-icon">{role === 'human' ? '👤' : '◈'}</span>
        {role === 'human' ? 'You' : 'Deepdive'}
      </div>
      <div className="message-content">
        {isLoading && !content ? (
          <div className="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        ) : (
          <ReactMarkdown>{content || '...'}</ReactMarkdown>
        )}
      </div>
      {role === 'assistant' && content && !isLoading && (
        <div className="message-actions">
          <button className="copy-btn" onClick={handleCopy} aria-label="Copy message">
            {copied ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>Copied</span>
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  )
}

export default MessageBubble
