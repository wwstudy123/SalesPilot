import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchCustomers } from '../lib/api/customers'
import type { Customer } from '../lib/types/api'
import './pages.css'

const STAGE_LABELS: Record<string, string> = {
  new: '新客',
  prospective: '意向',
  existing: '老客',
  churn_risk: '流失风险',
}

export function CustomersPage() {
  const customersQuery = useQuery({ queryKey: ['customers'], queryFn: fetchCustomers })

  const customers = customersQuery.data ?? []

  return (
    <div className='customers-page'>
      <section className='customers-page__header'>
        <h2>我的客户</h2>
        <span>共 {customers.length} 人</span>
      </section>

      {customersQuery.isLoading ? <p>加载中…</p> : null}
      {customersQuery.isError ? <p>加载失败：{(customersQuery.error as Error).message}</p> : null}
      {!customersQuery.isLoading && customers.length === 0 ? (
        <p>暂无客户。请先执行 <code>make seed</code> 灌入种子数据后重新登录。</p>
      ) : null}

      <ul className='customers-page__list'>
        {customers.map((customer: Customer) => (
          <li key={customer.id} className='customers-page__item panel'>
            <div className='customers-page__item-main'>
              <strong>{customer.name}</strong>
              <span className='customers-page__meta'>
                {STAGE_LABELS[customer.lifecycleStage] ?? customer.lifecycleStage}
                {customer.phone ? ` · ${customer.phone}` : ''}
                {customer.source ? ` · 来源：${customer.source}` : ''}
              </span>
              {customer.remark ? <p>{customer.remark}</p> : null}
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
