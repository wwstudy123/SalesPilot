import { apiFetch, buildQuery } from './client'
import { getToken } from './customers'

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

// ---------- M5：知识库（检索测试 / 入库 / 统计） ----------

export type KbHit = {
  label: string
  chunk_id: number
  title: string
  content: string
  score: number
  rrf: number
  hedge: boolean
}

export type KbSearchResult = {
  query: string
  rewritten: string
  mode: 'listwise' | 'rrf'
  hits: KbHit[]
}

export type KbStats = {
  docs: Array<{ domain: string; status: string; count: number }>
  ready_chunks: number
  vector_backend: 'milvus' | 'lite'
}

export type KbUploadResult = {
  ingested: { doc_id: number; domain: string; version: number; chunk_count: number }
  published: { domain: string; source: string; published: number } | null
  ready: boolean
}

export async function searchKb(params: { q: string; domain?: 'playbook' | 'product'; topK?: number }) {
  const query = buildQuery({ q: params.q, domain: params.domain, top_k: params.topK })
  return aiFetch<KbSearchResult>(`/api/ai/kb/search${query}`)
}

export async function fetchKbStats() {
  return aiFetch<KbStats>('/api/ai/kb/stats')
}

export async function seedKb() {
  return aiFetch<{ published: number; stats: KbStats }>('/api/ai/kb/seed', { method: 'POST' })
}

export async function uploadKb(body: {
  domain: 'playbook' | 'product'
  title: string
  texts: string[]
  source?: string
  publish?: boolean
}) {
  return aiFetch<KbUploadResult>('/api/ai/kb/upload', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
