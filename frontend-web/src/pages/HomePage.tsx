import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, BookOpen, MessageSquare, UserRound } from 'lucide-react'
import { fetchCustomers, fetchCustomerTags } from '../lib/api/customers'
import type { Customer, CustomerTag } from '../lib/types/api'
import './pages.css'

const STAGE_LABELS: Record<string, string> = {
  new: '新客',
  prospective: '意向',
  existing: '老客',
  churn_risk: '流失风险',
}

/** 工作台 Dashboard：客户概览 + 重点关注 + 快捷入口。 */
export function HomePage() {
  const navigate = useNavigate()
  const customersQuery = useQuery({
    queryKey: ['customers-with-tags'],
    queryFn: async () => {
      const customers = await fetchCustomers()
      return Promise.all(
        customers.map(async (customer) => ({ customer, tags: await fetchCustomerTags(customer.id) })),
      )
    },
  })

  const rows = customersQuery.data ?? []
  const total = rows.length
  const stageCounts = rows.reduce<Record<string, number>>((acc, { customer }) => {
    acc[customer.lifecycleStage] = (acc[customer.lifecycleStage] ?? 0) + 1
    return acc
  }, {})
  // 重点关注：流失风险 > 意向 > 新客（老客排后）
  const focusOrder: Record<string, number> = { churn_risk: 0, prospective: 1, new: 2, existing: 3 }
  const focus = [...rows]
    .sort((a, b) => (focusOrder[a.customer.lifecycleStage] ?? 9) - (focusOrder[b.customer.lifecycleStage] ?? 9))
    .slice(0, 6)

  return (
    <div className='dashboard'>
      <header className='dashboard__header'>
        <h1>工作台</h1>
        <p>今日重点客户与快捷操作，一屏掌握。</p>
      </header>

      <section className='dashboard__stats'>
        <div className='stat-card panel'>
          <span className='stat-card__label'>客户总数</span>
          <strong className='stat-card__value'>{customersQuery.isLoading ? '—' : total}</strong>
        </div>
        {Object.entries(STAGE_LABELS).map(([stage, label]) => (
          <div key={stage} className='stat-card panel'>
            <span className='stat-card__label'>{label}</span>
            <strong className='stat-card__value'>{stageCounts[stage] ?? 0}</strong>
          </div>
        ))}
      </section>

      <div className='dashboard__grid'>
        <section className='focus panel'>
          <div className='focus__head'>
            <h2>重点关注</h2>
            <Link to='/customers' className='focus__more'>
              全部客户 <ArrowRight size={14} />
            </Link>
          </div>
          {customersQuery.isLoading ? <p className='dashboard__empty'>加载中…</p> : null}
          {customersQuery.isError ? (
            <p className='dashboard__empty'>加载失败：{(customersQuery.error as Error).message}</p>
          ) : null}
          {!customersQuery.isLoading && total === 0 ? (
            <p className='dashboard__empty'>
              暂无客户数据，请先 <code>make seed</code> 灌入种子并重新登录。
            </p>
          ) : null}
          <ul className='focus__list'>
            {focus.map(({ customer, tags }: { customer: Customer; tags: CustomerTag[] }) => (
              <li key={customer.id}>
                <button
                  type='button'
                  className='focus__item'
                  onClick={() => navigate(`/customers/${customer.id}`)}
                >
                  <span className='focus__avatar'>{customer.name.slice(0, 1)}</span>
                  <span className='focus__info'>
                    <strong>{customer.name}</strong>
                    <span className='focus__meta'>
                      {STAGE_LABELS[customer.lifecycleStage] ?? customer.lifecycleStage}
                      {tags.length > 0 ? ` · ${tags.map((tag) => tag.tagName).join(' / ')}` : ''}
                    </span>
                  </span>
                  <ArrowRight size={15} className='focus__arrow' />
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className='shortcuts panel'>
          <div className='shortcuts__head'>
            <h2>快捷操作</h2>
          </div>
          <div className='shortcuts__grid'>
            <button type='button' className='shortcut' onClick={() => navigate('/chat')}>
              <span className='shortcut__icon'>
                <MessageSquare size={20} />
              </span>
              <span className='shortcut__text'>
                <strong>写回访话术</strong>
                <span>AI 助手按客户画像生成建议</span>
              </span>
            </button>
            <button type='button' className='shortcut' onClick={() => navigate('/chat')}>
              <span className='shortcut__icon'>
                <UserRound size={20} />
              </span>
              <span className='shortcut__text'>
                <strong>异议处理</strong>
                <span>客户说贵了 / 再考虑时求助</span>
              </span>
            </button>
            <button type='button' className='shortcut' onClick={() => navigate('/kb')}>
              <span className='shortcut__icon'>
                <BookOpen size={20} />
              </span>
              <span className='shortcut__text'>
                <strong>知识库检索</strong>
                <span>验证话术/产品知识命中</span>
              </span>
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}
