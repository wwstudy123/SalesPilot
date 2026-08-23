import { apiFetch } from './client'
import { getToken } from './customers'
import type { Suggestion } from '../types/api'

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

// ---------- SSE 聊天（M5 全量事件协议） ----------

export type ChatEvent =
  | { type: 'start'; run_id: string; session_id: string }
  | { type: 'intent'; intent: string; confidence: number; decision_path: string; reason: string }
  | { type: 'tool_call'; tool: string; ok: boolean; code?: string }
  | { type: 'rag_citation'; citations: Array<{ label: string; chunk_id: number; title: string; score: number }> }
  | { type: 'token'; content: string }
  | { type: 'proposal'; suggestion_id: number; skill: string; warnings: string[]; citations: unknown[] }
  | { type: 'done'; run_id: string; intent: string; status: string; echo: boolean }
  | { type: 'error'; message: string }

export interface ChatParams {
  message: string
  sessionId?: string
  customerId?: number
  intent?: string
}

export async function streamChat(params: ChatParams, onEvent: (event: ChatEvent) => void): Promise<void> {
  const token = getToken()
  const resp = await fetch('/api/ai/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      message: params.message,
      session_id: params.sessionId,
      customer_id: params.customerId,
      intent: params.intent,
    }),
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`chat 请求失败：${resp.status}`)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const line = frame.trim()
      if (!line.startsWith('data:')) {
        continue
      }
      onEvent(JSON.parse(line.slice(5).trim()) as ChatEvent)
    }
  }
}

// ---------- 建议卡（采纳可编辑 / 重新生成≤2 / 拒绝必填原因） ----------

export async function adoptSuggestion(suggestionId: number, editedContent?: string) {
  return aiFetch<Suggestion>(`/api/ai/suggestions/${suggestionId}/adopt`, {
    method: 'POST',
    body: JSON.stringify(editedContent ? { edited_content: editedContent } : {}),
  })
}

export async function rejectSuggestion(suggestionId: number, reason: string) {
  return aiFetch<Suggestion>(`/api/ai/suggestions/${suggestionId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

export async function regenerateSuggestion(suggestionId: number, requirement: string) {
  return aiFetch<Suggestion>(`/api/ai/suggestions/${suggestionId}/regenerate`, {
    method: 'POST',
    body: JSON.stringify({ requirement }),
  })
}
