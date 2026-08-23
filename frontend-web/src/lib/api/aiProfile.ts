import { apiFetch } from './client'
import { getToken } from './customers'
import type { ProfileRefreshResult, Proposal } from '../types/api'

/** sale-agent（/api/ai → vite 代理 → :8000），携员工 JWT。 */
function aiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  return apiFetch<T>(path, {
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  })
}

export async function fetchProposals(customerId: number, status?: string) {
  const query = new URLSearchParams({ customer_id: String(customerId) })
  if (status) {
    query.set('status', status)
  }
  return aiFetch<Proposal[]>(`/api/ai/proposals?${query.toString()}`)
}

export async function confirmProposal(proposalId: string) {
  return aiFetch<{ proposal: Proposal; profile_fields: unknown[] }>(`/api/ai/proposals/${proposalId}/confirm`, {
    method: 'POST',
  })
}

export async function rejectProposal(proposalId: string) {
  return aiFetch<{ proposal: Proposal }>(`/api/ai/proposals/${proposalId}/reject`, { method: 'POST' })
}

export async function refreshProfile(customerId: number, employeeId: number) {
  return aiFetch<ProfileRefreshResult>('/api/ai/profile/refresh', {
    method: 'POST',
    body: JSON.stringify({ customer_id: customerId, employee_id: employeeId }),
  })
}

export const FIELD_KEY_LABELS: Record<string, string> = {
  preference: '兴趣偏好',
  demand: '需求',
  value_tier: '价值分层',
  lifecycle_stage: '生命周期',
  sensitive_point: '敏感点',
  recent_focus: '近期关注',
}
