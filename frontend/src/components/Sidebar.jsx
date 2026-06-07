import './Sidebar.css'

function Sidebar({ history, activeSession, onSelect, onDelete, onNewSession, isOpen, onClose, isLoading }) {
  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-top">
        <div className="sidebar-brand">
          <span className="brand-icon">◈</span>
          <span className="brand-text">Deepdive</span>
        </div>
        <button className="sidebar-close" onClick={onClose} aria-label="Close menu">✕</button>
      </div>

      <button className="new-chat-btn" onClick={onNewSession} disabled={isLoading}>
        <span>+</span> New Chat
      </button>

      <div className="sidebar-section-label">Recent</div>

      {history.length === 0 ? (
        <div className="sidebar-empty">No conversations yet</div>
      ) : (
        <div className="sidebar-list">
          {history.map((item) => {
            const isActive = item.session_id === activeSession
            const isReloading = isActive && isLoading
            return (
              <div
                key={item.session_id}
                className={`sidebar-item ${isActive ? 'active' : ''} ${isReloading ? 'reloading' : ''}`}
                onClick={() => !isLoading && onSelect(item)}
              >
                <div className="sidebar-item-icon">
                  {isReloading ? (
                    <span className="sidebar-spinner" />
                  ) : (
                    <>
                      {item.source_type === 'YouTube' && '▶'}
                      {item.source_type === 'PDF' && '📄'}
                      {item.source_type === 'Webpage' && '🌐'}
                      {item.source_type === 'Document' && '📋'}
                    </>
                  )}
                </div>
                <div className="sidebar-item-info">
                  <div className="sidebar-item-title">
                    {item.label}
                  </div>
                  <div className="sidebar-item-meta">
                    {isReloading ? 'Reloading…' : item.source_type}
                  </div>
                </div>
                {!isReloading && (
                  <button
                    className="sidebar-item-delete"
                    onClick={(e) => { e.stopPropagation(); onDelete(item.session_id); }}
                    aria-label="Delete"
                  >
                    ×
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </aside>
  )
}

export default Sidebar
