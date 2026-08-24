import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMe, fetchProfileFields } from '../../lib/api/customers'
import {
  FIELD_KEY_LABELS,
  confirmProposal,
  fetchProposals,
  refreshProfile,
  rejectProposal,
} from '../../lib/api/aiProfile'
import type { ProfileRefreshResult, ProposalField, TagProposalField } from '../../lib/types/api'
import { formatDate } from '../../lib/utils/format'

/** AI 画像面板：画像卡 + HITL 确认面板 + 新客首访采集清单（M4）。 */
export function ProfilePanel({ customerId }: { customerId: number }) {
  const queryClient = useQueryClient()
  const [notice, setNotice] = useState<string | null>(null)
  const [checklist, setChecklist] = useState<string[] | null>(null)

  const meQuery = useQuery({ queryKey: ['me'], queryFn: fetchMe })
  const profileQuery = useQuery({
    queryKey: ['profile-fields', customerId],
    queryFn: () => fetchProfileFields(customerId),
    enabled: Number.isFinite(customerId),
  })
  // 10s 轮询：补录跟进后事件链路自动出提案，无需刷新页面
  const proposalsQuery = useQuery({
    queryKey: ['proposals', customerId],
    queryFn: () => fetchProposals(customerId, 'pending'),
    enabled: Number.isFinite(customerId),
    refetchInterval: 10_000,
  })

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['proposals', customerId] })
    queryClient.invalidateQueries({ queryKey: ['profile-fields', customerId] })
  }

  const refreshMutation = useMutation({
    mutationFn: () => refreshProfile(customerId, meQuery.data?.id ?? 0),
    onSuccess: (result: ProfileRefreshResult) => {
      setChecklist(null)
      if (result.outcome === 'proposal') {
        setNotice(`已生成更新提案（${result.proposal?.fields.length ?? 0} 个字段），请确认`)
      } else if (result.outcome === 'no_change') {
        setNotice('画像已是最新，无变更')
      } else if (result.outcome === 'first_visit_checklist') {
        setNotice(`跟进记录不足（${result.record_count ?? 0} 条），请先按清单采集`)
        setChecklist(result.checklist ?? [])
      } else {
        setNotice(`分析失败：${result.error ?? '未知错误'}`)
      }
      invalidateAll()
    },
    onError: (error: Error) => setNotice(`分析失败：${error.message}`),
  })

  const confirmMutation = useMutation({
    mutationFn: confirmProposal,
    onSuccess: () => {
      setNotice('已确认，画像字段已更新')
      invalidateAll()
    },
    onError: (error: Error) => setNotice(`确认失败：${error.message}`),
  })

  const rejectMutation = useMutation({
    mutationFn: rejectProposal,
    onSuccess: () => {
      setNotice('已放弃该提案')
      invalidateAll()
    },
    onError: (error: Error) => setNotice(`操作失败：${error.message}`),
  })

  const pending = (proposalsQuery.data ?? []).filter((proposal) => proposal.tool === 'update_profile_field')
  const fields = profileQuery.data ?? []
  const busy = refreshMutation.isPending || confirmMutation.isPending || rejectMutation.isPending

  return (
    <section className='panel profile-panel'>
      <div className='profile-panel__header'>
        <h3>AI 客户画像</h3>
        <button
          className='profile-panel__refresh'
          disabled={busy || !meQuery.data}
          onClick={() => refreshMutation.mutate()}
        >
          {refreshMutation.isPending ? '分析中…' : '重新分析'}
        </button>
      </div>

      {notice ? <p className='profile-panel__notice'>{notice}</p> : null}

      {pending.map((proposal) => (
        <div key={proposal.id} className='profile-proposal'>
          <div className='profile-proposal__head'>
            <strong>待确认更新提案</strong>
            <span>
              {proposal.source ?? '手动'} · {formatDate(proposal.expires_at)} 前有效
            </span>
          </div>
          <ul className='profile-proposal__fields'>
            {proposal.fields.filter(isProfileField).map((field) => (
              <li key={field.fieldKey}>
                <span className='profile-field__key'>{FIELD_KEY_LABELS[field.fieldKey] ?? field.fieldKey}</span>
                <p className='profile-field__value'>
                  {field.oldValue ? (
                    <>
                      <del>{field.oldValue}</del> → {field.fieldValue}
                    </>
                  ) : (
                    field.fieldValue
                  )}
                </p>
                <span className='profile-field__evidence'>依据：{field.evidence}</span>
              </li>
            ))}
          </ul>
          <div className='profile-proposal__actions'>
            <button
              className='profile-proposal__confirm'
              disabled={busy}
              onClick={() => confirmMutation.mutate(proposal.id)}
            >
              确认写入
            </button>
            <button
              className='profile-proposal__reject'
              disabled={busy}
              onClick={() => rejectMutation.mutate(proposal.id)}
            >
              放弃
            </button>
          </div>
        </div>
      ))}

      {checklist ? (
        <div className='profile-checklist'>
          <strong>新客首访采集清单</strong>
          <ul>
            {checklist.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {profileQuery.isLoading ? <p>加载中…</p> : null}
      {fields.length === 0 && !profileQuery.isLoading && !checklist ? (
        <p className='profile-panel__empty'>暂无画像字段，补录跟进后 AI 将自动生成提案。</p>
      ) : null}

      <ul className='profile-panel__fields'>
        {fields.map((field) => (
          <li key={field.id}>
            <span className='profile-field__key'>{FIELD_KEY_LABELS[field.fieldKey] ?? field.fieldKey}</span>
            <p className='profile-field__value'>{field.fieldValue}</p>
            <span className='profile-field__evidence'>
              {field.evidence ? `依据：${field.evidence} · ` : ''}
              v{field.version} · {field.updatedAt ? formatDate(field.updatedAt) : '-'}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function isProfileField(field: ProposalField | TagProposalField): field is ProposalField {
  return 'fieldKey' in field
}
