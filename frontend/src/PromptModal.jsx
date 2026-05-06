import { useEffect, useRef, useState } from 'react'

export default function PromptModal({ initialValue = '', onClose, onSave }) {
  const [value, setValue] = useState(initialValue)
  const textareaRef = useRef(null)

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>System Prompt</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal-body">
          <p className="field-hint" style={{ marginTop: 0 }}>
            This is the instruction the LLM will receive every turn. Describe the
            agent's role, tone, and any rules it must follow.
          </p>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="You are a helpful assistant that..."
          />
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={() => {
              onSave(value)
              onClose()
            }}
          >
            Save Prompt
          </button>
        </div>
      </div>
    </div>
  )
}
