import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import AgentForm from './AgentForm.jsx'
import PaymentPage from './PaymentPage.jsx'

export default function App() {
  const paymentMatch = window.location.pathname.match(/^\/pay\/([^/]+)/)
  if (paymentMatch) {
    return <PaymentPage paymentId={decodeURIComponent(paymentMatch[1])} />
  }

  return <AgentBuilder />
}

function AgentBuilder() {
  const [agents, setAgents] = useState([])
  const [models, setModels] = useState([])
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [conversationError, setConversationError] = useState('')

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const refresh = async () => {
    try {
      setListError('')
      const [list, history] = await Promise.all([
        api.listAgents(),
        api.listConversations(),
      ])
      setAgents(list)
      setConversations(history)
    } catch (err) {
      setListError(err.message)
    }
  }

  const refreshConversations = async () => {
    try {
      setConversationError('')
      setConversations(await api.listConversations())
    } catch (err) {
      setConversationError(err.message)
    }
  }

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const [list, modelList, history] = await Promise.all([
          api.listAgents(),
          api.listModels(),
          api.listConversations(),
        ])
        if (!cancelled) {
          setAgents(list)
          setModels(modelList)
          setConversations(history)
        }
      } catch (err) {
        if (!cancelled) setListError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const interval = window.setInterval(refreshConversations, 5000)
    return () => window.clearInterval(interval)
  }, [])

  const agentsById = useMemo(
    () => Object.fromEntries(agents.map((a) => [a.id, a])),
    [agents],
  )

  const activeConversation = conversations[0] || null

  const openCreate = () => {
    setEditing(null)
    setFormError('')
    setShowForm(true)
  }

  const openEdit = (agent) => {
    setEditing(agent)
    setFormError('')
    setShowForm(true)
  }

  const closeForm = () => {
    setShowForm(false)
    setEditing(null)
    setFormError('')
  }

  const handleSubmit = async (payload) => {
    setSaving(true)
    setFormError('')
    try {
      if (editing) {
        await api.updateAgent(editing.id, payload)
      } else {
        await api.createAgent(payload)
      }
      await refresh()
      closeForm()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (agent) => {
    if (!confirm(`Delete agent "${agent.name}"? This cannot be undone.`)) return
    try {
      await api.deleteAgent(agent.id)
      await refresh()
    } catch (err) {
      alert(`Failed to delete: ${err.message}`)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Agent Builder</h1>
          <p>Create Claude-powered agents with custom prompts and sub-agent delegation.</p>
        </div>
        <button className="btn btn-primary" onClick={openCreate}>
          + New Agent
        </button>
      </header>

      {listError && <div className="error" style={{ marginBottom: 16 }}>{listError}</div>}

      <section className="history-panel">
        <div className="history-header">
          <div>
            <h2>Active Conversation</h2>
            <p>
              Persisted in <code>config/conversation_history.json</code>
              {activeConversation
                ? ` for ${agentsById[activeConversation.agent_id]?.name || activeConversation.agent_id}`
                : ''}
            </p>
          </div>
          <button className="btn btn-secondary" onClick={refreshConversations}>
            Refresh
          </button>
        </div>

        {conversationError && <div className="error">{conversationError}</div>}

        {!activeConversation ? (
          <div className="history-empty">No conversation history has been recorded yet.</div>
        ) : (
          <>
            <div className="history-meta">
              <span>{activeConversation.phone_number}</span>
              <span>{activeConversation.messages.length} messages</span>
              <span>Updated {new Date(activeConversation.updated_at).toLocaleString()}</span>
            </div>
            <div className="history-messages">
              {activeConversation.messages.length === 0 ? (
                <div className="history-empty">This session is active, but no turns have been saved yet.</div>
              ) : (
                activeConversation.messages.map((message) => (
                  <article key={message.id} className={`history-message ${message.role}`}>
                    <div className="history-message-meta">
                      <span>{message.role === 'user' ? 'User' : 'Assistant'}</span>
                      <span>{new Date(message.created_at).toLocaleTimeString()}</span>
                    </div>
                    <p>{message.content}</p>
                    {message.metadata?.delegated_to && (
                      <span className="badge badge-muted">
                        Delegated to {message.metadata.delegated_to}
                      </span>
                    )}
                  </article>
                ))
              )}
            </div>
          </>
        )}
      </section>

      {loading ? (
        <div className="empty">
          <div className="spinner" style={{ borderTopColor: 'var(--accent)' }} />
          <p>Loading agents…</p>
        </div>
      ) : agents.length === 0 ? (
        <div className="empty">
          <h2>No agents yet</h2>
          <p>Create your first agent to get started.</p>
          <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={openCreate}>
            + New Agent
          </button>
        </div>
      ) : (
        <div className="grid">
          {agents.map((agent) => (
            <div key={agent.id} className="card">
              <div className="card-title">
                <h3>{agent.name}</h3>
                <span className="badge">{agent.model}</span>
              </div>
              <p className="card-prompt">
                {agent.system_prompt?.trim() || 'No system prompt set.'}
              </p>
              <div className="card-meta">
                <div className="card-meta-row">
                  <span>Sub-agents</span>
                  <span>
                    {agent.sub_agent_ids.length === 0
                      ? 'None'
                      : agent.sub_agent_ids
                          .map((id) => agentsById[id]?.name || '?')
                          .join(', ')}
                  </span>
                </div>
                <div className="card-meta-row">
                  <span>Updated</span>
                  <span>{new Date(agent.updated_at).toLocaleString()}</span>
                </div>
              </div>
              <div className="card-actions">
                <button className="btn btn-secondary" onClick={() => openEdit(agent)}>
                  Edit
                </button>
                <button className="btn btn-danger" onClick={() => handleDelete(agent)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <AgentForm
          initial={editing}
          models={models}
          agents={agents}
          onClose={closeForm}
          onSubmit={handleSubmit}
          saving={saving}
          error={formError}
        />
      )}
    </div>
  )
}
