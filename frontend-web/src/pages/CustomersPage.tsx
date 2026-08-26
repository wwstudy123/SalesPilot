import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MessageSquare, Search, X } from 'lucide-react'
import { createCustomer, fetchCustomers, fetchCustomerTags, fetchFollowUps } from '../lib/api/customers'
import { formatDate } from '../lib/utils/format'
import type { Customer, CustomerTag, FollowUp } from '../lib/types/api'
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

const PAGE_SIZE = 8

type Row = { customer: Customer; tags: CustomerTag[]; latestFollowUp?: FollowUp }

export function CustomersPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [stage, setStage] = useState('')
  const [tagKey, setTagKey] = useState('')
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({
    name: '',
    phone: '',
    gender: 'U',
    lifecycleStage: 'new',
    source: '',
    remark: '',
  })

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

  const createMutation = useMutation({
    mutationFn: () =>
      createCustomer({
        name: form.name.trim(),
        phone: form.phone.trim() || undefined,
        gender: form.gender as 'M' | 'F' | 'U',
        lifecycleStage: form.lifecycleStage as 'new' | 'prospective' | 'existing' | 'churn_risk',
        source: form.source.trim() || undefined,
        remark: form.remark.trim() || undefined,
      }),
    onSuccess: () => {
      setCreating(false)
      setForm({ name: '', phone: '', gender: 'U', lifecycleStage: 'new', source: '', remark: '' })
      void queryClient.invalidateQueries({ queryKey: ['customers-with-tags'] })
    },
  })

  const rows = customersQuery.data ?? []
  const availableTags = new Map<string, string>()
  rows.forEach(({ tags }) => tags.forEach((tag) => availableTags.set(tag.tagKey, tag.tagName)))

  const filtered = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return rows.filter(({ customer, tags }) => {
      if (stage && customer.lifecycleStage !== stage) {
        return false
      }
      if (tagKey && !tags.some((tag) => tag.tagKey === tagKey)) {
        return false
      }
      if (
        keyword &&
        !customer.name.toLowerCase().includes(keyword) &&
        !(customer.phone ?? '').toLowerCase().includes(keyword)
      ) {
        return false
      }
      return true
    })
  }, [rows, search, stage, tagKey])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount)
  const paged = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  return (
    <div className='customers-page'>
      <div className='customers-page__toolbar'>
        <div className='customers-page__search'>
          <Search size={15} />
          <input
            value={search}
            placeholder='搜索姓名 / 电话'
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
            }}
          />
        </div>
        <select className='select' value={stage} onChange={(event) => { setStage(event.target.value); setPage(1) }}>
          <option value=''>全部意向</option>
          {Object.entries(STAGE_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <select className='select' value={tagKey} onChange={(event) => { setTagKey(event.target.value); setPage(1) }}>
          <option value=''>全部标签</option>
          {[...availableTags.entries()].map(([key, name]) => (
            <option key={key} value={key}>
              {name}
            </option>
          ))}
        </select>
        <button type='button' className='primary-button' onClick={() => setCreating(true)}>
          新建客户
        </button>
      </div>

      {customersQuery.isLoading ? <p className='page-empty'>加载中…</p> : null}
      {customersQuery.isError ? <p className='page-empty'>加载失败：{(customersQuery.error as Error).message}</p> : null}
      {!customersQuery.isLoading && !customersQuery.isError && filtered.length === 0 ? (
        <p className='page-empty'>暂无匹配客户</p>
      ) : null}

      {paged.length > 0 ? (
        <div className='panel customers-table-wrap'>
          <table className='customers-table'>
            <thead>
              <tr>
                <th>客户</th>
                <th>阶段</th>
                <th>最近跟进</th>
                <th>标签</th>
                <th>来源</th>
                <th className='customers-table__actions-head'>操作</th>
              </tr>
            </thead>
            <tbody>
              {paged.map(({ customer, tags, latestFollowUp }) => (
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
                  <td className='customers-table__phone'>
                    {latestFollowUp ? (
                      <>
                        {formatDate(latestFollowUp.createdAt)}
                        {latestFollowUp.nextFollowAt ? (
                          <em className='customers-table__next'>下次 {formatDate(latestFollowUp.nextFollowAt)}</em>
                        ) : null}
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
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

          {filtered.length > PAGE_SIZE ? (
            <div className='pagination'>
              <button
                type='button'
                className='secondary-button secondary-button--small'
                disabled={safePage <= 1}
                onClick={() => setPage(safePage - 1)}
              >
                上一页
              </button>
              <span className='pagination__info'>
                {safePage} / {pageCount}（共 {filtered.length} 条）
              </span>
              <button
                type='button'
                className='secondary-button secondary-button--small'
                disabled={safePage >= pageCount}
                onClick={() => setPage(safePage + 1)}
              >
                下一页
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      {creating ? (
        <div className='modal-backdrop' onClick={() => setCreating(false)}>
          <div className='modal' onClick={(event) => event.stopPropagation()}>
            <div className='modal__head'>
              <h3>新建客户</h3>
              <button type='button' className='modal__close' onClick={() => setCreating(false)}>
                <X size={16} />
              </button>
            </div>
            <div className='modal__body'>
              <label className='form-field'>
                <span>姓名 *</span>
                <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
              </label>
              <label className='form-field'>
                <span>电话</span>
                <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
              </label>
              <label className='form-field'>
                <span>性别</span>
                <select value={form.gender} onChange={(event) => setForm({ ...form, gender: event.target.value })}>
                  <option value='U'>未知</option>
                  <option value='M'>男</option>
                  <option value='F'>女</option>
                </select>
              </label>
              <label className='form-field'>
                <span>意向阶段</span>
                <select
                  value={form.lifecycleStage}
                  onChange={(event) => setForm({ ...form, lifecycleStage: event.target.value })}
                >
                  {Object.entries(STAGE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className='form-field'>
                <span>来源</span>
                <input value={form.source} onChange={(event) => setForm({ ...form, source: event.target.value })} />
              </label>
              <label className='form-field'>
                <span>备注</span>
                <input value={form.remark} onChange={(event) => setForm({ ...form, remark: event.target.value })} />
              </label>
            </div>
            <div className='modal__foot'>
              <button type='button' className='secondary-button' onClick={() => setCreating(false)}>
                取消
              </button>
              <button
                type='button'
                className='primary-button'
                disabled={!form.name.trim() || createMutation.isPending}
                onClick={() => createMutation.mutate()}
              >
                {createMutation.isPending ? '创建中…' : '创建'}
              </button>
            </div>
            {createMutation.isError ? (
              <p className='modal__notice'>创建失败：{(createMutation.error as Error).message}</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
