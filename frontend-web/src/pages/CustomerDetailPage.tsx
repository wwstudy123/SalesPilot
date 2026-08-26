import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchCustomer, fetchFollowUps, fetchMe, fetchPurchases } from '../lib/api/customers'
import { refreshProfile } from '../lib/api/aiProfile'
import { ProfilePanel } from '../components/profile/ProfilePanel'
import { TagPanel } from '../components/tags/TagPanel'
import { formatDate } from '../lib/utils/format'
import './pages.css'

const STAGE_LABELS: Record<string, string> = {
  new: '新客',
  prospective: '意向',
  existing: '老客',
  churn_risk: '流失风险',
}

export function CustomerDetailPage() {
  const { customerId } = useParams()
  const id = Number(customerId)
  const queryClient = useQueryClient()

  const customerQuery = useQuery({
    queryKey: ['customer', id],
    queryFn: () => fetchCustomer(id),
    enabled: Number.isFinite(id),
  })
  const followUpsQuery = useQuery({
    queryKey: ['follow-ups', id],
    queryFn: () => fetchFollowUps(id),
    enabled: Number.isFinite(id),
  })
  const purchasesQuery = useQuery({
    queryKey: ['purchases', id],
    queryFn: () => fetchPurchases(id),
    enabled: Number.isFinite(id),
  })
  const meQuery = useQuery({ queryKey: ['me'], queryFn: fetchMe })

  const profileRefresh = useMutation({
    mutationFn: () => refreshProfile(id, meQuery.data?.id ?? 0),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile-fields', id] })
      queryClient.invalidateQueries({ queryKey: ['proposals', id] })
    },
  })

  const customer = customerQuery.data

  return (
    <div className='customer-detail'>
      <p>
        <Link to='/customers'>← 返回客户列表</Link>
      </p>

      {customerQuery.isError ? <p>加载失败：{(customerQuery.error as Error).message}</p> : null}

      {customer ? (
        <section className='panel profile-hero'>
          <div className='profile-hero__main'>
            <span className='profile-hero__avatar'>{customer.name.slice(0, 1)}</span>
            <div className='profile-hero__title'>
              <h2>{customer.name}</h2>
              <p className='profile-hero__meta'>
                {STAGE_LABELS[customer.lifecycleStage] ?? customer.lifecycleStage}
                {customer.gender ? ` · ${customer.gender === 'male' ? '男' : customer.gender === 'female' ? '女' : customer.gender}` : ''}
                {customer.phone ? ` · ${customer.phone}` : ''}
                {customer.source ? ` · 来源：${customer.source}` : ''}
              </p>
            </div>
            <div className='profile-hero__actions'>
              <button
                type='button'
                className='primary-button primary-button--small'
                disabled={profileRefresh.isPending || !meQuery.data}
                onClick={() => profileRefresh.mutate()}
              >
                {profileRefresh.isPending ? '分析中…' : 'AI 生成画像'}
              </button>
              <Link className='secondary-button secondary-button--small' to={`/chat?customerId=${customer.id}`}>
                AI 生成话术
              </Link>
            </div>
          </div>
          {customer.remark ? <p className='profile-hero__remark'>备注：{customer.remark}</p> : null}

          <div className='profile-hero__grid'>
            <ProfilePanel customerId={id} />
            <TagPanel customerId={id} />
          </div>
        </section>
      ) : null}

      <div className='customer-detail__columns'>
        <section className='panel'>
          <h3>跟进时间线（{followUpsQuery.data?.length ?? 0}）</h3>
          {followUpsQuery.isLoading ? <p>加载中…</p> : null}
          <ul className='customer-detail__timeline'>
            {(followUpsQuery.data ?? []).map((followUp) => (
              <li key={followUp.id}>
                <span className='customer-detail__timeline-time'>
                  {formatDate(followUp.createdAt)} · {followUp.channel}
                </span>
                <p>{followUp.content}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className='panel'>
          <h3>消费记录（{purchasesQuery.data?.length ?? 0}）</h3>
          {purchasesQuery.isLoading ? <p>加载中…</p> : null}
          <ul className='customer-detail__purchases'>
            {(purchasesQuery.data ?? []).map((purchase) => (
              <li key={purchase.id}>
                <strong>{purchase.productName}</strong>
                <span>
                  {purchase.category} · ¥{Number(purchase.amount).toFixed(2)} × {purchase.quantity}
                </span>
                <span className='customer-detail__timeline-time'>{formatDate(purchase.purchasedAt)}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
