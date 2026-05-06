const BASE = '/api/agents'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch (_) {
      // ignore parse errors
    }
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  listAgents: () => request(''),
  createAgent: (payload) =>
    request('', { method: 'POST', body: JSON.stringify(payload) }),
  updateAgent: (id, payload) =>
    request(`/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteAgent: (id) => request(`/${id}`, { method: 'DELETE' }),
  listModels: () => request('/models'),
  listConversations: () => request('/conversations'),
}
