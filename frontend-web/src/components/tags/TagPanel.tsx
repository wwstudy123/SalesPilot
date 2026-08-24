import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { confirmProposal, editTagProposal, fetchProposals, rejectProposal, reviewTags } from '../../lib/api/aiProfile'
import { fetchCustomerTags } from '../../lib/api/customers'
import type { TagProposalField } from '../../lib/types/api'

function isTagField(field: unknown): field is TagProposalField {
  return typeof field === 'object' && field !== null && 'tagKey' in field
}

/** M6 标签建议卡：确认、修正后确认或放弃；确认后立即刷新当前标签。 */
export function TagPanel({ customerId }: { customerId: number }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const tagsQuery = useQuery({ queryKey: ['customer-tags', customerId], queryFn: () => fetchCustomerTags(customerId) })
  const proposalsQuery = useQuery({
    queryKey: ['proposals', customerId],
    queryFn: () => fetchProposals(customerId, 'pending'),
    refetchInterval: 10_000,
  })
  const proposal = useMemo(() => (proposalsQuery.data ?? []).find((item) => item.tool === 'save_tags'), [proposalsQuery.data])
  const [draft, setDraft] = useState<TagProposalField[]>([])
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['customer-tags', customerId] })
    queryClient.invalidateQueries({ queryKey: ['proposals', customerId] })
  }
  const confirm = useMutation({ mutationFn: confirmProposal, onSuccess: invalidate })
  const reject = useMutation({ mutationFn: rejectProposal, onSuccess: invalidate })
  const edit = useMutation({ mutationFn: ({ id, tags }: { id: string; tags: TagProposalField[] }) => editTagProposal(id, tags), onSuccess: invalidate })
  const review = useMutation({ mutationFn: () => reviewTags(customerId), onSuccess: invalidate })
  const suggestion = (proposal?.fields ?? []).filter(isTagField)
  const busy = confirm.isPending || reject.isPending || edit.isPending || review.isPending

  return (
    <section className='panel tag-panel'>
      <div className='profile-panel__header'>
        <h3>客户标签</h3>
        <span>{tagsQuery.data?.length ?? 0} 个已生效</span>
        <button className='secondary-button' disabled={busy} onClick={() => review.mutate()}>
          {review.isPending ? '分析中…' : '重新打标'}
        </button>
      </div>
      <div className='tag-panel__active'>
        {(tagsQuery.data ?? []).map((tag) => (
          <span key={tag.id} title={`依据：${tag.evidence}`}>
            {tag.tagName}
          </span>
        ))}
        {!tagsQuery.isLoading && (tagsQuery.data ?? []).length === 0 ? <p>暂无已生效标签</p> : null}
      </div>
      {proposal ? (
        <div className='profile-proposal'>
          <strong>待确认标签建议</strong>
          {(editing ? draft : suggestion).map((tag, index) => (
            <div key={`${tag.tagKey}-${index}`} className='tag-panel__suggestion'>
              {editing ? (
                <>
                  <input
                    value={tag.tagKey}
                    onChange={(event) =>
                      setDraft((items) => items.map((item, i) => (i === index ? { ...item, tagKey: event.target.value } : item)))
                    }
                  />
                  <input
                    value={tag.evidence}
                    onChange={(event) =>
                      setDraft((items) => items.map((item, i) => (i === index ? { ...item, evidence: event.target.value } : item)))
                    }
                  />
                </>
              ) : (
                <>
                  <strong>{tag.tagKey}</strong>
                  <span>依据：{tag.evidence}</span>
                  <span>置信度：{tag.confidence}</span>
                </>
              )}
            </div>
          ))}
          <div className='profile-proposal__actions'>
            {editing ? (
              <button disabled={busy} onClick={() => edit.mutate({ id: proposal.id, tags: draft })}>
                保存修正
              </button>
            ) : (
              <button disabled={busy} onClick={() => confirm.mutate(proposal.id)}>
                确认生效
              </button>
            )}
            <button
              className='secondary-button'
              disabled={busy}
              onClick={() => {
                setDraft(suggestion)
                setEditing(!editing)
              }}
            >
              {editing ? '取消修正' : '修正标签'}
            </button>
            <button className='danger-button' disabled={busy} onClick={() => reject.mutate(proposal.id)}>
              放弃
            </button>
          </div>
        </div>
      ) : null}
    </section>
  )
}
