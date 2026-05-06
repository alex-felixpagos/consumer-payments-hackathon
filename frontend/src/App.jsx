import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import AgentForm from './AgentForm.jsx'

export default function App() {
  const [agents, setAgents] = useState([])
  const [models, setModels] = useState([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const refresh = async () => {
    try {
      setListError('')
      const list = await api.listAgents()
      setAgents(list)
    } catch (err) {
      setListError(err.message)
    }
  }

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const [list, modelList] = await Promise.all([
          api.listAgents(),
          api.listModels(),
        ])
        if (!cancelled) {
          setAgents(list)
          setModels(modelList)
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

  const agentsById = useMemo(
    () => Object.fromEntries(agents.map((a) => [a.id, a])),
    [agents],
  )

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
