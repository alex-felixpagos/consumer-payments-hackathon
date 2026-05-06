const AGENTS_BASE = '/api/agents'
const API_BASE = '/api'

async function request(base, path, options = {}) {
  const res = await fetch(`${base}${path}`, {
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
  listAgents: () => request(AGENTS_BASE, ''),
  createAgent: (payload) =>
    request(AGENTS_BASE, '', { method: 'POST', body: JSON.stringify(payload) }),
  updateAgent: (id, payload) =>
    request(AGENTS_BASE, `/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteAgent: (id) => request(AGENTS_BASE, `/${id}`, { method: 'DELETE' }),
  listModels: () => request(AGENTS_BASE, '/models'),
  listConversations: () => request(AGENTS_BASE, '/conversations'),
}

export const paymentsApi = {
  getPayment: (id) => request(API_BASE, `/payments/${id}`),
  submitPayment: (id, payload) =>
    request(API_BASE, `/payments/${id}/pay`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}
