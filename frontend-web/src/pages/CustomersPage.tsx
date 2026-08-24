import { Link } from 'react-router-dom'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MessageSquare } from 'lucide-react'
import { fetchCustomers, fetchCustomerTags } from '../lib/api/customers'
import type { Customer, CustomerTag } from '../lib/types/api'
import './pages.css'

const STAGE_LABELS: Record<string, string> = {
  new: '新客',
  prospective: '意向',
  existing: '老客',
  churn_risk: '流失风险',
}

const STAGE_CLASS: Record<string, string> = {
  new: 'stage-badge stage-badge--new',
  prospective: 'stage-badge stage-badge--prospective',
  existing: 'stage-badge stage-badge--existing',
  churn_risk: 'stage-badge stage-badge--risk',
}

export function CustomersPage() {
  const [tagKey, setTagKey] = useState('')
  const customersQuery = useQuery({
    queryKey: ['customers-with-tags'],
    queryFn: async () => {
      const customers = await fetchCustomers()
      return Promise.all(customers.map(async (customer) => ({ customer, tags: await fetchCustomerTags(customer.id) })))
    },
  })

  const customers = customersQuery.data ?? []
  const availableTags = new Map<string, string>()
  customers.forEach(({ tags }) => tags.forEach((tag) => availableTags.set(tag.tagKey, tag.tagName)))
  const filtered = tagKey ? customers.filter(({ tags }) => tags.some((tag) => tag.tagKey === tagKey)) : customers

  return (
    <div className='customers-page'>
      <header className='page-header'>
        <div>
          <h1>我的客户</h1>
          <p className='page-header__sub'>共 {filtered.length} 人{tagKey ? `（筛选：${availableTags.get(tagKey) ?? tagKey}）` : ''}</p>
        </div>
        <select className='select customers-page__filter' value={tagKey} onChange={(event) => setTagKey(event.target.value)}>
          <option value=''>全部标签</option>
          {[...availableTags.entries()].map(([key, name]) => (
            <option key={key} value={key}>
              {name}
            </option>
          ))}
        </select>
      </header>

      {customersQuery.isLoading ? <p className='page-empty'>加载中…</p> : null}
      {customersQuery.isError ? <p className='page-empty'>加载失败：{(customersQuery.error as Error).message}</p> : null}
      {!customersQuery.isLoading && customers.length === 0 ? (
        <p className='page-empty'>暂无客户。请先执行 <code>make seed</code> 灌入种子数据后重新登录。</p>
      ) : null}

      {filtered.length > 0 ? (
        <div className='panel customers-table-wrap'>
          <table className='customers-table'>
            <thead>
              <tr>
                <th>客户</th>
                <th>阶段</th>
                <th>电话</th>
                <th>标签</th>
                <th>来源</th>
                <th className='customers-table__actions-head'>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(({ customer, tags }: { customer: Customer; tags: CustomerTag[] }) => (
                <tr key={customer.id}>
                  <td>
                    <Link className='customers-table__name' to={`/customers/${customer.id}`}>
                      <span className='customers-table__avatar'>{customer.name.slice(0, 1)}</span>
                      <span>
                        <strong>{customer.name}</strong>
                        {customer.remark ? <em className='customers-table__remark'>{customer.remark}</em> : null}
                      </span>
                    </Link>
                  </td>
                  <td>
                    <span className={STAGE_CLASS[customer.lifecycleStage] ?? 'stage-badge'}>
                      {STAGE_LABELS[customer.lifecycleStage] ?? customer.lifecycleStage}
                    </span>
                  </td>
                  <td className='customers-table__phone'>{customer.phone || '—'}</td>
                  <td>
                    {tags.length > 0 ? (
                      <span className='tag-chips'>
                        {tags.map((tag) => (
                          <span key={tag.tagKey} className='tag-chip'>
                            {tag.tagName}
                          </span>
                        ))}
                      </span>
                    ) : (
                      <span className='customers-table__phone'>—</span>
                    )}
                  </td>
                  <td className='customers-table__phone'>{customer.source || '—'}</td>
                  <td>
                    <div className='customers-table__actions'>
                      <Link className='secondary-button secondary-button--small' to={`/chat?customerId=${customer.id}`}>
                        <MessageSquare size={14} />
                        写话术
                      </Link>
                      <Link className='secondary-button secondary-button--small' to={`/customers/${customer.id}`}>
                        详情
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}
