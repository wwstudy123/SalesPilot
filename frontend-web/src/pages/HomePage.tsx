import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, BookOpen, MessageSquare, UserRound } from 'lucide-react'
import { fetchCustomers, fetchCustomerTags, fetchFollowUps } from '../lib/api/customers'
import { formatDate } from '../lib/utils/format'
import type { Customer, CustomerTag, FollowUp } from '../lib/types/api'
import './pages.css'

const STAGE_LABELS: Record<string, string> = {
  new: '新客',
  prospective: '意向',
  existing: '老客',
  churn_risk: '流失风险',
}

const STAGE_DOT_CLASS: Record<string, string> = {
  new: 'focus__dot--new',
  prospective: 'focus__dot--prospective',
  existing: 'focus__dot--existing',
  churn_risk: 'focus__dot--risk',
}

const STAGE_AVATAR_CLASS: Record<string, string> = {
  new: 'focus__avatar--new',
  prospective: 'focus__avatar--prospective',
  existing: 'focus__avatar--existing',
  churn_risk: 'focus__avatar--risk',
}

const STAGE_ITEM_CLASS: Record<string, string> = {
  new: 'focus__item--new',
  prospective: 'focus__item--prospective',
  existing: 'focus__item--existing',
  churn_risk: 'focus__item--risk',
}

type Row = { customer: Customer; tags: CustomerTag[]; latestFollowUp?: FollowUp }

/** 工作台 Dashboard：4 统计卡（含 30 天趋势）+ 重点关注 + 快捷入口（带意图跳转）。 */
export function HomePage() {
  const navigate = useNavigate()
  const customersQuery = useQuery({
    queryKey: ['customers-with-tags'],
    queryFn: async (): Promise<Row[]> => {
      const customers = await fetchCustomers()
      return Promise.all(
        customers.map(async (customer) => {
          const [tags, followUps] = await Promise.all([fetchCustomerTags(customer.id), fetchFollowUps(customer.id)])
          const sorted = [...followUps].sort((a, b) => (b.createdAt ?? '').localeCompare(a.createdAt ?? ''))
          return { customer, tags, latestFollowUp: sorted[0] }
        }),
      )
    },
  })

  const rows = customersQuery.data ?? []
  const total = rows.length

  const weekNew = useMemo(() => {
    const now = new Date()
    const day = (now.getDay() + 6) % 7 // 周一=0
    const monday = new Date(now)
    monday.setHours(0, 0, 0, 0)
    monday.setDate(now.getDate() - day)
    return rows.filter(({ customer }) => {
      if (!customer.createdAt) {
        return false
      }
      const created = new Date(customer.createdAt)
      return created >= monday && created <= now
    }).length
  }, [rows])

  const prospective = useMemo(() => rows.filter(({ customer }) => customer.lifecycleStage === 'prospective').length, [rows])

  const pendingFollow = useMemo(
    () => rows.filter(({ latestFollowUp }) => Boolean(latestFollowUp?.nextFollowAt)).length,
    [rows],
  )

  // 30 天新增趋势（按 createdAt 分桶）
  const trend = useMemo(() => {
    const buckets = new Array<number>(30).fill(0)
    const end = new Date()
    end.setHours(23, 59, 59, 999)
    const start = new Date(end)
    start.setDate(start.getDate() - 29)
    start.setHours(0, 0, 0, 0)
    rows.forEach(({ customer }) => {
      if (!customer.createdAt) {
        return
      }
      const created = new Date(customer.createdAt)
      if (created < start || created > end) {
        return
      }
      const idx = Math.floor((created.getTime() - start.getTime()) / 86_400_000)
      buckets[Math.min(idx, 29)] += 1
    })
    return buckets
  }, [rows])

  const trendMax = Math.max(...trend, 1)

  // 重点关注：流失风险 > 意向 > 新客 > 老客
  const focusOrder: Record<string, number> = { churn_risk: 0, prospective: 1, new: 2, existing: 3 }
  const focus = [...rows]
    .sort((a, b) => (focusOrder[a.customer.lifecycleStage] ?? 9) - (focusOrder[b.customer.lifecycleStage] ?? 9))
    .slice(0, 6)

  const stats: Array<{ label: string; value: number; hint: string }> = [
    { label: '客户总数', value: total, hint: '累计客户' },
    { label: '本周新增', value: weekNew, hint: '近 7 天' },
    { label: '意向客户', value: prospective, hint: '意向阶段' },
    { label: '待跟进', value: pendingFollow, hint: '有下次跟进计划' },
  ]

  return (
    <div className='dashboard'>
      <section className='dashboard__stats'>
        {stats.map((stat) => (
          <div key={stat.label} className='stat-card panel'>
            <span className='stat-card__label'>{stat.label}</span>
            <strong className='stat-card__value'>{customersQuery.isLoading ? '—' : stat.value}</strong>
            <span className='stat-card__hint'>{stat.hint}</span>
            <span className='stat-card__trend' aria-hidden='true'>
              {trend.map((count, index) => (
                <i key={index} style={{ height: `${Math.max(8, (count / trendMax) * 100)}%` }} />
              ))}
            </span>
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
          {!customersQuery.isLoading && !customersQuery.isError && total === 0 ? (
            <p className='dashboard__empty'>暂无客户数据</p>
          ) : null}
          <ul className='focus__list'>
            {focus.map(({ customer, tags, latestFollowUp }) => (
              <li key={customer.id}>
                <button
                  type='button'
                  className={`focus__item ${STAGE_ITEM_CLASS[customer.lifecycleStage] ?? ''}`}
                  onClick={() => navigate(`/customers/${customer.id}`)}
                >
                  <span className={`focus__dot ${STAGE_DOT_CLASS[customer.lifecycleStage] ?? ''}`} />
                  <span className={`focus__avatar ${STAGE_AVATAR_CLASS[customer.lifecycleStage] ?? ''}`}>
                    {customer.name.slice(0, 1)}
                  </span>
                  <span className='focus__info'>
                    <strong>{customer.name}</strong>
                    <span className='focus__meta'>
                      {STAGE_LABELS[customer.lifecycleStage] ?? customer.lifecycleStage}
                      {customer.source ? ` · ${customer.source}` : ''}
                      {tags.length > 0 ? ` · ${tags.map((tag) => tag.tagName).join(' / ')}` : ''}
                    </span>
                    <span className='focus__extra'>
                      {latestFollowUp
                        ? `最近跟进：${formatDate(latestFollowUp.createdAt)}`
                        : '暂无跟进'}
                      {latestFollowUp?.nextFollowAt ? ` · 下次跟进：${formatDate(latestFollowUp.nextFollowAt)}` : ''}
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
            <button type='button' className='shortcut' onClick={() => navigate('/chat?intent=talk_script')}>
              <span className='shortcut__icon'>
                <MessageSquare size={20} />
              </span>
              <span className='shortcut__text'>
                <strong>写回访话术</strong>
                <span>AI 助手按客户画像生成建议</span>
              </span>
            </button>
            <button type='button' className='shortcut' onClick={() => navigate('/chat?intent=objection_help')}>
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
