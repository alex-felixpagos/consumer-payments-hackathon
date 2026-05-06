import { useEffect, useMemo, useState } from 'react'
import PromptModal from './PromptModal.jsx'

export default function AgentForm({
  initial,
  models,
  agents,
  onClose,
  onSubmit,
  saving,
  error,
}) {
  const isEdit = Boolean(initial?.id)
  const [name, setName] = useState(initial?.name || '')
  const [systemPrompt, setSystemPrompt] = useState(initial?.system_prompt || '')
  const [model, setModel] = useState(initial?.model || models[0]?.id || '')
  const [subAgentIds, setSubAgentIds] = useState(initial?.sub_agent_ids || [])
  const [showPromptModal, setShowPromptModal] = useState(false)

  const modelOptions = useMemo(() => {
    if (!initial?.model || models.some((m) => m.id === initial.model)) return models
    return [{ id: initial.model, display_name: initial.model }, ...models]
  }, [initial?.model, models])

  useEffect(() => {
    if (!model && modelOptions[0]?.id) {
      setModel(modelOptions[0].id)
    }
  }, [model, modelOptions])

  const modelLabel = (modelInfo) => {
    if (!modelInfo.display_name || modelInfo.display_name === modelInfo.id) return modelInfo.id
    return `${modelInfo.display_name} (${modelInfo.id})`
  }

  const promptPreview = systemPrompt.trim()
    ? systemPrompt.slice(0, 80) + (systemPrompt.length > 80 ? '…' : '')
    : 'Click to write a system prompt'

  const promptCharCount = systemPrompt.length

  const candidateSubAgents = agents.filter((a) => a.id !== initial?.id)

  const toggleSubAgent = (id) => {
    setSubAgentIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!name.trim()) return
    onSubmit({
      name: name.trim(),
      system_prompt: systemPrompt,
      model,
      sub_agent_ids: subAgentIds,
    })
  }

  return (
    <>
      <div className="modal-backdrop" onClick={onClose}>
        <div className="modal" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2>{isEdit ? 'Edit Agent' : 'New Agent'}</h2>
            <button className="modal-close" onClick={onClose} aria-label="Close">
              ×
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="modal-body">
              <div>
                <label className="field-label" htmlFor="agent-name">
                  Name
                </label>
                <input
                  id="agent-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Customer Support"
                  required
                  autoFocus
                />
              </div>

              <div>
                <label className="field-label" htmlFor="agent-model">
                  Model
                </label>
                <select
                  id="agent-model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                >
                  {modelOptions.map((m) => (
                    <option key={m.id} value={m.id}>
                      {modelLabel(m)}
                    </option>
                  ))}
                </select>
                <p className="field-hint">
                  Models are fetched from Anthropic with your configured API key.
                </p>
              </div>

              <div>
                <label className="field-label">System Prompt</label>
                <button
                  type="button"
                  className="prompt-trigger"
                  onClick={() => setShowPromptModal(true)}
                >
                  <span className="prompt-preview">{promptPreview}</span>
                  <span className="arrow">
                    {promptCharCount > 0 ? `${promptCharCount} chars ›` : 'Edit ›'}
                  </span>
                </button>
              </div>

              <div>
                <label className="field-label">Sub-agents (delegation targets)</label>
                {candidateSubAgents.length === 0 ? (
                  <p className="field-hint" style={{ marginTop: 0 }}>
                    Create another agent first to enable delegation.
                  </p>
                ) : (
                  <div className="subagent-list">
                    {candidateSubAgents.map((a) => (
                      <label key={a.id} className="subagent-row">
                        <input
                          type="checkbox"
                          checked={subAgentIds.includes(a.id)}
                          onChange={() => toggleSubAgent(a.id)}
                        />
                        <span className="name">{a.name}</span>
                        <span className="model">{a.model}</span>
                      </label>
                    ))}
                  </div>
                )}
                <p className="field-hint">
                  The LLM can transfer the conversation to any selected sub-agent.
                </p>
              </div>

              {error && <div className="error">{error}</div>}
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onClose}
                disabled={saving}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={saving || !name.trim() || !model}
              >
                {saving ? <span className="spinner" /> : isEdit ? 'Save changes' : 'Create agent'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {showPromptModal && (
        <PromptModal
          initialValue={systemPrompt}
          onClose={() => setShowPromptModal(false)}
          onSave={setSystemPrompt}
        />
      )}
    </>
  )
}
