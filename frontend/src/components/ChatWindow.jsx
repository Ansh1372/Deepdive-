import { useState, useRef, useEffect } from 'react'
import { chatStream } from '../api'
import MessageBubble from './MessageBubble'
import SourcePanel from './SourcePanel'
import PipelinePanel from './PipelinePanel'
import './ChatWindow.css'

const CHAT_STORAGE_KEY = 'deepdive_chat_'

function ChatWindow({ sessionId, isReady, isCached, onNewSession }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sources, setSources] = useState([])
  const [pipeline, setPipeline] = useState(null)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  const examplePrompts = [
    "Summarize the main points",
    "What are the key takeaways?",
    "Explain the most important concepts",
  ]

  // Load chat history from localStorage when session changes
  useEffect(() => {
    const saved = localStorage.getItem(CHAT_STORAGE_KEY + sessionId)
    if (saved) {
      try {
        setMessages(JSON.parse(saved))
      } catch {
        setMessages([])
      }
    } else {
      setMessages([])
    }
    setSources([])
    setPipeline(null)
  }, [sessionId])

  // Save messages to localStorage whenever they change
  useEffect(() => {
    if (messages.length > 0 && !isLoading) {
      localStorage.setItem(CHAT_STORAGE_KEY + sessionId, JSON.stringify(messages))
    }
  }, [messages, isLoading, sessionId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px'
    }
  }, [input])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const question = input.trim()
    setInput('')
    setSources([])
    setPipeline(null)
    setMessages((prev) => [...prev, { role: 'human', content: question }])
    setIsLoading(true)

    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    try {
      await chatStream(
        question,
        sessionId,
        (chunk) => {
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: updated[updated.length - 1].content + chunk,
            }
            return updated
          })
        },
        (newSources) => setSources(newSources),
        () => setIsLoading(false),
        (pipelineData) => setPipeline(pipelineData)
      )
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: `Error: ${err.message}`,
        }
        return updated
      })
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend(e)
    }
  }

  const handleExport = () => {
    if (messages.length === 0) return

    const markdown = messages.map((msg) => {
      const label = msg.role === 'human' ? '**You**' : '**Deepdive**'
      return `${label}\n\n${msg.content}`
    }).join('\n\n---\n\n')

    const header = `# Deepdive Chat Export\n\nExported: ${new Date().toLocaleString()}\n\n---\n\n`
    const content = header + markdown

    const blob = new Blob([content], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `deepdive-chat-${sessionId.slice(0, 6)}-${Date.now()}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleClearChat = () => {
    setMessages([])
    setSources([])
    setPipeline(null)
    localStorage.removeItem(CHAT_STORAGE_KEY + sessionId)
  }

  return (
    <div className="chat-window">
      <div className="chat-header">
        <div className="chat-header-left">
          {isReady && <span className="status-dot" />}
          {isCached && <span className="cache-badge">cached</span>}
        </div>
        <div className="chat-header-right">
          {messages.length > 0 && (
            <>
              <button className="header-btn" onClick={handleExport} title="Export chat as markdown">
                ⬇ Export
              </button>
              <button className="header-btn clear-btn" onClick={handleClearChat} title="Clear chat history">
                🗑 Clear
              </button>
            </>
          )}
          <button className="new-btn" onClick={onNewSession}>+ New source</button>
        </div>
      </div>

      <div className="messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">💬</div>
            <p className="empty-title">Ask anything about your content</p>
            <div className="prompt-cards">
              {examplePrompts.map((prompt, i) => (
                <button
                  key={i}
                  className="prompt-card"
                  onClick={() => setInput(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="messages-inner">
          {messages.map((msg, i) => (
            <MessageBubble
              key={i}
              role={msg.role}
              content={msg.content}
              isLoading={isLoading && i === messages.length - 1 && msg.role === 'assistant'}
            />
          ))}
          {pipeline && <PipelinePanel pipeline={pipeline} />}
          {sources.length > 0 && <SourcePanel sources={sources} />}
        </div>
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-container">
        <form className="chat-input" onSubmit={handleSend}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question..."
            disabled={isLoading}
            rows={1}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="send-btn"
            aria-label="Send"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  )
}

export default ChatWindow
