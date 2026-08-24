import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchCustomer, fetchFollowUps, fetchPurchases } from '../lib/api/customers'
import { ProfilePanel } from '../components/profile/ProfilePanel'
import { TagPanel } from '../components/tags/TagPanel'
import { formatDate } from '../lib/utils/format'
import './pages.css'

export function CustomerDetailPage() {
  const { customerId } = useParams()
  const id = Number(customerId)

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

  const customer = customerQuery.data

  return (
    <div className='customer-detail'>
      <p>
        <Link to='/customers'>← 返回客户列表</Link>
      </p>

      {customerQuery.isError ? <p>加载失败：{(customerQuery.error as Error).message}</p> : null}

      {customer ? (
        <section className='panel'>
          <h2>{customer.name}</h2>
          <p className='customer-detail__meta'>
            阶段：{customer.lifecycleStage} · 性别：{customer.gender}
            {customer.phone ? ` · 电话：${customer.phone}` : ''}
            {customer.source ? ` · 来源：${customer.source}` : ''}
          </p>
          {customer.remark ? <p>备注：{customer.remark}</p> : null}
          <Link className='secondary-button' to={`/chat?customerId=${customer.id}`}>
            用 AI 生成回访话术
          </Link>
        </section>
      ) : null}

      <div className='customer-detail__columns'>
        <ProfilePanel customerId={id} />
        <TagPanel customerId={id} />

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
