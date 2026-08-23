import { useState } from 'react'
import { adoptSuggestion, regenerateSuggestion, rejectSuggestion } from '../../lib/api/aiChat'
import type { SuggestionCitation } from '../../lib/types/api'

export interface SuggestionCardProps {
  suggestionId: number
  skill: string
  content: string
  citations: SuggestionCitation[]
  warnings: string[]
}

type CardStatus = 'pending' | 'adopted' | 'modified' | 'rejected'

const REGENERATE_LIMIT = 2

/** 话术建议卡：采纳(可编辑) / 重新生成(≤2,附要求) / 拒绝(必填原因)。 */
export function SuggestionCard(props: SuggestionCardProps) {
  const [status, setStatus] = useState<CardStatus>('pending')
  const [content, setContent] = useState(props.content)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(props.content)
  const [requirement, setRequirement] = useState('')
  const [reason, setReason] = useState('')
  const [regenCount, setRegenCount] = useState(0)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setNotice(null)
    try {
      await action()
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function handleAdopt() {
    return run(async () => {
      const edited = editing ? draft : undefined
      await adoptSuggestion(props.suggestionId, edited)
      if (edited) {
        setContent(edited)
      }
      setStatus(edited && edited !== content ? 'modified' : 'adopted')
    })
  }

  function handleRegenerate() {
    if (!requirement.trim()) {
      setNotice('请填写重新生成要求')
      return
    }
    return run(async () => {
      const updated = await regenerateSuggestion(props.suggestionId, requirement.trim())
      setContent(updated.content)
      setDraft(updated.content)
      setRegenCount(updated.regenerate_count)
      setRequirement('')
      setNotice(`已按新要求重新生成（${updated.regenerate_count}/${REGENERATE_LIMIT}）`)
    })
  }

  function handleReject() {
    if (!reason.trim()) {
      setNotice('拒绝必须填写原因')
      return
    }
    return run(async () => {
      await rejectSuggestion(props.suggestionId, reason.trim())
      setStatus('rejected')
    })
  }

  return (
    <div className={`suggestion-card suggestion-card--${status}`}>
      <header className='suggestion-card__header'>
        <span className='suggestion-card__skill'>{props.skill}</span>
        <span className='suggestion-card__status'>{statusLabel(status)}</span>
      </header>

      <div className='suggestion-card__content'>
        {editing ? (
          <textarea value={draft} onChange={(event) => setDraft(event.target.value)} rows={8} />
        ) : (
          <pre>{content}</pre>
        )}
      </div>

      {props.warnings.length > 0 ? (
        <ul className='suggestion-card__warnings'>
          {props.warnings.map((warning) => (
            <li key={warning}>⚠ {warning}</li>
          ))}
        </ul>
      ) : null}

      {props.citations.length > 0 ? (
        <ul className='suggestion-card__citations'>
          {props.citations.map((citation) => (
            <li key={citation.label}>
              [{citation.label}] {citation.title}（{citation.score}）
            </li>
          ))}
        </ul>
      ) : null}

      {status === 'pending' ? (
        <div className='suggestion-card__actions'>
          <button type='button' onClick={handleAdopt} disabled={busy}>
            {editing ? '保存并采纳' : '采纳'}
          </button>
          <button type='button' className='secondary-button' onClick={() => setEditing(!editing)} disabled={busy}>
            {editing ? '取消编辑' : '编辑后采纳'}
          </button>
          <button
            type='button'
            className='secondary-button'
            onClick={handleRegenerate}
            disabled={busy || regenCount >= REGENERATE_LIMIT}
          >
            重新生成（{REGENERATE_LIMIT - regenCount} 次可用）
          </button>
          <button type='button' className='danger-button' onClick={handleReject} disabled={busy}>
            拒绝
          </button>
        </div>
      ) : null}

      {status === 'pending' ? (
        <div className='suggestion-card__inputs'>
          <input
            placeholder='重新生成要求，例如：更口语化一些'
            value={requirement}
            onChange={(event) => setRequirement(event.target.value)}
            disabled={busy || regenCount >= REGENERATE_LIMIT}
          />
          <input
            placeholder='拒绝原因（必填）'
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            disabled={busy}
          />
        </div>
      ) : null}

      {notice ? <p className='suggestion-card__notice'>{notice}</p> : null}
    </div>
  )
}

function statusLabel(status: CardStatus): string {
  switch (status) {
    case 'adopted':
      return '已采纳'
    case 'modified':
      return '已修改采纳'
    case 'rejected':
      return '已拒绝'
    default:
      return '待处理'
  }
}
