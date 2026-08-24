import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { streamChat, type ChatEvent } from '../lib/api/aiChat'
import { fetchCustomers } from '../lib/api/customers'
import { SuggestionCard } from '../components/chat/SuggestionCard'
import type { Customer, SuggestionCitation } from '../lib/types/api'
import './pages.css'

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  meta: string[]
  citations: SuggestionCitation[]
  warnings: string[]
  suggestionId?: number
  skill?: string
}

const QUICK_INTENTS: Array<{ intent: string; label: string; fallback: string }> = [
  { intent: 'talk_script', label: '写回访话术', fallback: '帮我写一段回访话术' },
  { intent: 'objection_help', label: '异议处理求助', fallback: '客户有顾虑，帮我处理异议' },
]

/** 员工侧聊天窗（sidebar 形态）：SSE 全量事件渲染 + 建议卡交互。 */
export function ChatPage() {
  const [searchParams] = useSearchParams()
  const customersQuery = useQuery({ queryKey: ['customers'], queryFn: fetchCustomers })
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [customerId, setCustomerId] = useState<string>(() => searchParams.get('customerId') ?? '')
  const [streaming, setStreaming] = useState(false)
  const sessionId = useRef(`chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`)

  function patchLastMessage(patch: (message: ChatMessage) => ChatMessage) {
    setMessages((prev) => {
      const last = prev[prev.length - 1]
      if (!last || last.role !== 'assistant') {
        return prev
      }
      return [...prev.slice(0, -1), patch(last)]
    })
  }

  function handleEvent(event: ChatEvent) {
    switch (event.type) {
      case 'intent':
        patchLastMessage((message) => ({
          ...message,
          meta: [...message.meta, `意图：${event.intent}（${event.decision_path}，置信度 ${event.confidence}）`],
        }))
        break
      case 'tool_call':
        patchLastMessage((message) => ({
          ...message,
          meta: [...message.meta, `工具：${event.tool} ${event.ok ? '✓' : `✗ ${event.code ?? ''}`}`],
        }))
        break
      case 'rag_citation':
        patchLastMessage((message) => ({ ...message, citations: event.citations }))
        break
      case 'token':
        patchLastMessage((message) => ({ ...message, content: message.content + event.content }))
        break
      case 'proposal':
        patchLastMessage((message) => ({
          ...message,
          suggestionId: event.suggestion_id,
          skill: event.skill,
          warnings: event.warnings,
        }))
        break
      case 'error':
        patchLastMessage((message) => ({ ...message, content: `出错了：${event.message}` }))
        break
      default:
        break
    }
  }

  async function send(menuIntent?: string, fallbackMessage?: string) {
    const message = input.trim() || fallbackMessage
    if (!message || streaming) {
      return
    }
    setInput('')
    setStreaming(true)
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: message, meta: [], citations: [], warnings: [] },
      { role: 'assistant', content: '', meta: [], citations: [], warnings: [] },
    ])
    try {
      await streamChat(
        {
          message,
          sessionId: sessionId.current,
          customerId: customerId ? Number(customerId) : undefined,
          intent: menuIntent,
        },
        handleEvent,
      )
    } catch (error) {
      patchLastMessage((message) => ({ ...message, content: `请求失败：${(error as Error).message}` }))
    } finally {
      setStreaming(false)
    }
  }

  const customers = (customersQuery.data ?? []) as Customer[]

  return (
    <div className='chat-page'>
      <section className='chat-page__header'>
        <h2>AI 话术助手</h2>
        <select value={customerId} onChange={(event) => setCustomerId(event.target.value)}>
          <option value=''>不指定客户（通用建议）</option>
          {customers.map((customer) => (
            <option key={customer.id} value={customer.id}>
              {customer.name}
            </option>
          ))}
        </select>
      </section>

      <div className='chat-page__messages'>
        {messages.length === 0 ? (
          <p className='chat-page__empty'>选择客户后，输入诉求或点击下方场景按钮，AI 将生成带引用的话术建议卡。</p>
        ) : null}
        {messages.map((message, index) => (
          <div key={index} className={`chat-page__bubble chat-page__bubble--${message.role}`}>
            {message.meta.length > 0 ? (
              <ul className='chat-page__meta'>
                {message.meta.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : null}
            {message.content ? <pre className='chat-page__text'>{message.content}</pre> : null}
            {message.role === 'assistant' && streaming && index === messages.length - 1 && !message.content ? (
              <span className='chat-page__typing'>生成中…</span>
            ) : null}
            {message.suggestionId ? (
              <SuggestionCard
                suggestionId={message.suggestionId}
                skill={message.skill ?? ''}
                content={message.content}
                citations={message.citations}
                warnings={message.warnings}
              />
            ) : null}
            {message.citations.length > 0 && !message.suggestionId ? (
              <ul className='chat-page__citations'>
                {message.citations.map((citation) => (
                  <li key={citation.label}>
                    [{citation.label}] {citation.title}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </div>

      <div className='chat-page__composer'>
        <div className='chat-page__quick'>
          {QUICK_INTENTS.map((quick) => (
            <button
              key={quick.intent}
              type='button'
              className='secondary-button'
              disabled={streaming}
              onClick={() => send(quick.intent, quick.fallback)}
            >
              {quick.label}
            </button>
          ))}
        </div>
        <div className='chat-page__input-row'>
          <input
            value={input}
            placeholder='例如：给王女士写一段回访话术 / 客户说太贵了怎么办'
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                void send()
              }
            }}
            disabled={streaming}
          />
          <button type='button' onClick={() => send()} disabled={streaming || !input.trim()}>
            发送
          </button>
        </div>
      </div>
    </div>
  )
}
