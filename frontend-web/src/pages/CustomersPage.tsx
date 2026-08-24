import { Link } from 'react-router-dom'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCustomers, fetchCustomerTags } from '../lib/api/customers'
import type { Customer, CustomerTag } from '../lib/types/api'
import './pages.css'

const STAGE_LABELS: Record<string, string> = {
  new: '新客',
  prospective: '意向',
  existing: '老客',
  churn_risk: '流失风险',
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
      <section className='customers-page__header'>
        <h2>我的客户</h2>
        <span>共 {filtered.length} 人</span>
        <select value={tagKey} onChange={(event) => setTagKey(event.target.value)}>
          <option value=''>全部标签</option>
          {[...availableTags.entries()].map(([key, name]) => (
            <option key={key} value={key}>
              {name}
            </option>
          ))}
        </select>
      </section>

      {customersQuery.isLoading ? <p>加载中…</p> : null}
      {customersQuery.isError ? <p>加载失败：{(customersQuery.error as Error).message}</p> : null}
      {!customersQuery.isLoading && customers.length === 0 ? (
        <p>暂无客户。请先执行 <code>make seed</code> 灌入种子数据后重新登录。</p>
      ) : null}

      <ul className='customers-page__list'>
        {filtered.map(({ customer, tags }: { customer: Customer; tags: CustomerTag[] }) => (
          <li key={customer.id} className='customers-page__item panel'>
            <div className='customers-page__item-main'>
              <strong>{customer.name}</strong>
              <span className='customers-page__meta'>
                {STAGE_LABELS[customer.lifecycleStage] ?? customer.lifecycleStage}
                {customer.phone ? ` · ${customer.phone}` : ''}
                {customer.source ? ` · 来源：${customer.source}` : ''}
              </span>
              {customer.remark ? <p>{customer.remark}</p> : null}
              {tags.length > 0 ? <p>{tags.map((tag) => tag.tagName).join(' · ')}</p> : null}
            </div>
            <Link className='secondary-button' to={`/customers/${customer.id}`}>
              详情
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
