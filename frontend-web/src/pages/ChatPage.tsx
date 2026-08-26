import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, PanelRight } from 'lucide-react'
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

/** 5 类快捷意图（点击带入预设 prompt，后端自由识别路由）。 */
const QUICK_INTENTS: Array<{ key: string; label: string; prompt: string }> = [
  { key: 'customer_analysis', label: '客户分析', prompt: '帮我分析一下这位客户的情况、购买意向和潜在风险' },
  { key: 'product_consult', label: '产品咨询', prompt: '介绍一下我们的产品特点、卖点和适用场景' },
  { key: 'quote_query', label: '报价查询', prompt: '帮我查询产品的价格区间和当前优惠活动' },
  { key: 'follow_up_advice', label: '跟进建议', prompt: '给我一些客户跟进的建议和节奏安排' },
  { key: 'knowledge_qa', label: '知识问答', prompt: '基于知识库回答一个销售相关的问题' },
]

const INTENT_LABELS: Record<string, string> = {
  talk_script: '生成回访话术',
  objection_help: '异议处理',
  customer_analysis: '客户分析',
  product_consult: '产品咨询',
  quote_query: '报价查询',
  follow_up_advice: '跟进建议',
  knowledge_qa: '知识问答',
  recommend: '推荐建议',
  undefined: '意图识别',
}

type PanelIntent = { intent: string; confidence: number; decision_path: string }
type PanelTool = { tool: string; ok: boolean; code?: string }
type PanelCitation = { label: string; chunk_id: number; title: string; score: number }
type TaskState = { label: string; status: 'running' | 'done' | 'error' }

/** 员工侧聊天窗：SSE 全量事件 + 任务状态条 + 右侧可折叠技术面板 + 建议卡交互。 */
export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const customersQuery = useQuery({ queryKey: ['customers'], queryFn: fetchCustomers })
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [customerId, setCustomerId] = useState<string>(() => searchParams.get('customerId') ?? '')
  const [streaming, setStreaming] = useState(false)
  const [task, setTask] = useState<TaskState | null>(null)
  const [panelOpen, setPanelOpen] = useState(true)
  const [panel, setPanel] = useState<{ intents: PanelIntent[]; tools: PanelTool[]; citations: PanelCitation[] }>({
    intents: [],
    tools: [],
    citations: [],
  })
  const sessionId = useRef(`chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`)

  // 首次进入若带 intent 参数（来自工作台快捷入口），自动触发对应预设
  useEffect(() => {
    const intentParam = searchParams.get('intent')
    if (!intentParam || messages.length > 0) {
      return
    }
    const preset = QUICK_INTENTS.find((q) => q.key === intentParam)
    if (preset) {
      const next = new URLSearchParams(searchParams)
      next.delete('intent')
      setSearchParams(next, { replace: true })
      void send(preset.prompt)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
      case 'start':
        setTask({ label: '正在启动任务…', status: 'running' })
        break
      case 'intent':
        setPanel((prev) => ({
          ...prev,
          intents: [...prev.intents, { intent: event.intent, confidence: event.confidence, decision_path: event.decision_path }],
        }))
        setTask({ label: `正在执行：${INTENT_LABELS[event.intent] ?? event.intent}`, status: 'running' })
        patchLastMessage((message) => ({
          ...message,
          meta: [...message.meta, `意图：${event.intent}（${event.decision_path}，置信度 ${event.confidence}）`],
        }))
        break
      case 'tool_call':
        setPanel((prev) => ({ ...prev, tools: [...prev.tools, { tool: event.tool, ok: event.ok, code: event.code }] }))
        setTask({ label: `调用工具：${event.tool}`, status: 'running' })
        patchLastMessage((message) => ({
          ...message,
          meta: [...message.meta, `工具：${event.tool} ${event.ok ? '✓' : `✗ ${event.code ?? ''}`}`],
        }))
        break
      case 'rag_citation':
        setPanel((prev) => ({ ...prev, citations: [...prev.citations, ...event.citations] }))
        setTask({ label: '检索知识库，命中片段…', status: 'running' })
        patchLastMessage((message) => ({ ...message, citations: event.citations }))
        break
      case 'token':
        setTask({ label: '生成回答…', status: 'running' })
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
      case 'done':
        setTask({ label: '已完成', status: 'done' })
        break
      case 'error':
        setTask({ label: `执行失败：${event.message}`, status: 'error' })
        patchLastMessage((message) => ({ ...message, content: `出错了：${event.message}` }))
        break
      default:
        break
    }
  }

  async function send(prompt?: string) {
    const message = input.trim() || prompt
    if (!message || streaming) {
      return
    }
    setInput('')
    setStreaming(true)
    setTask({ label: '正在启动任务…', status: 'running' })
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
        },
        handleEvent,
      )
    } catch (error) {
      setTask({ label: '请求失败', status: 'error' })
      patchLastMessage((message) => ({ ...message, content: `请求失败：${(error as Error).message}` }))
    } finally {
      setStreaming(false)
    }
  }

  const customers = (customersQuery.data ?? []) as Customer[]
  const hasPanelContent = panel.intents.length > 0 || panel.tools.length > 0 || panel.citations.length > 0

  return (
    <div className='chat-page'>
      <div className='chat-page__main'>
        <div className='chat-page__col'>
          <div className='chat-page__toolbar'>
            <select value={customerId} onChange={(event) => setCustomerId(event.target.value)} disabled={streaming}>
              <option value=''>不指定客户（通用建议）</option>
              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.name}
                </option>
              ))}
            </select>
            {task ? (
              <span className={`chat-task chat-task--${task.status}`}>
                <i className='chat-task__bar' />
                {task.label}
              </span>
            ) : null}
          </div>

          <div className='chat-page__messages'>
            {messages.length === 0 ? (
              <p className='chat-page__empty'>
                选择客户后，输入诉求或点击下方场景按钮，AI 将生成带引用的话术建议卡。
              </p>
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
                  key={quick.key}
                  type='button'
                  className='secondary-button'
                  disabled={streaming}
                  onClick={() => void send(quick.prompt)}
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
              <button type='button' onClick={() => void send()} disabled={streaming || !input.trim()}>
                发送
              </button>
            </div>
          </div>
        </div>

        <aside className={`chat-panel ${panelOpen ? 'is-open' : ''}`}>
          <button
            type='button'
            className='chat-panel__toggle'
            onClick={() => setPanelOpen((open) => !open)}
            title={panelOpen ? '收起技术面板' : '展开技术面板'}
          >
            {panelOpen ? <ChevronRight size={16} /> : <PanelRight size={16} />}
          </button>
          {panelOpen ? (
            <div className='chat-panel__body'>
              <h3>执行链路</h3>
              {!hasPanelContent ? <p className='chat-panel__empty'>暂无数据，发送消息后展示意图 / 工具 / RAG 命中。</p> : null}

              <section className='chat-panel__section'>
                <h4>意图路由</h4>
                {panel.intents.length === 0 ? <p className='chat-panel__muted'>—</p> : null}
                {panel.intents.map((item, index) => (
                  <div key={index} className='chat-panel__row'>
                    <span>{INTENT_LABELS[item.intent] ?? item.intent}</span>
                    <em>{Math.round(item.confidence * 100)}%</em>
                  </div>
                ))}
              </section>

              <section className='chat-panel__section'>
                <h4>MCP / 工具调用</h4>
                {panel.tools.length === 0 ? <p className='chat-panel__muted'>—</p> : null}
                {panel.tools.map((item, index) => (
                  <div key={index} className='chat-panel__row'>
                    <span>{item.tool}</span>
                    <em className={item.ok ? 'is-ok' : 'is-bad'}>{item.ok ? '✓' : `✗ ${item.code ?? ''}`}</em>
                  </div>
                ))}
              </section>

              <section className='chat-panel__section'>
                <h4>RAG 命中来源</h4>
                {panel.citations.length === 0 ? <p className='chat-panel__muted'>—</p> : null}
                {panel.citations.map((item, index) => (
                  <div key={index} className='chat-panel__row chat-panel__row--stack'>
                    <span>
                      [{item.label}] {item.title}
                    </span>
                    <em>{item.score}</em>
                  </div>
                ))}
              </section>
            </div>
          ) : null}
        </aside>
      </div>
    </div>
  )
}
