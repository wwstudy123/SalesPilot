import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { createEmployee, fetchCustomers, fetchEmployees, transferCustomer, updateEmployeeRole } from '../lib/api/admin'
import { fetchAdminSessions } from '../lib/api/admin'
import './pages.css'

const INITIAL_FORM = { username: '', name: '', password: '', role: 'employee' as 'employee' | 'manager', phone: '' }

/** M7 管理端最小工作台：员工（建号/改角色）、全量客户与会话采纳监控。 */
export function AdminPage() {
  const queryClient = useQueryClient()
  const employees = useQuery({ queryKey: ['admin-employees'], queryFn: fetchEmployees })
  const customers = useQuery({ queryKey: ['admin-customers'], queryFn: fetchCustomers })
  const sessions = useQuery({ queryKey: ['admin-sessions'], queryFn: fetchAdminSessions })

  const [form, setForm] = useState(INITIAL_FORM)
  const [createError, setCreateError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: createEmployee,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-employees'] })
      setForm(INITIAL_FORM)
      setCreateError(null)
    },
    onError: (err) => setCreateError((err as Error).message),
  })

  const transfer = useMutation({
    mutationFn: ({ customerId, toEmployeeId }: { customerId: number; toEmployeeId: number }) => transferCustomer(customerId, toEmployeeId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-customers'] }),
  })
  const role = useMutation({
    mutationFn: ({ employeeId, role }: { employeeId: number; role: 'employee' | 'manager' }) => updateEmployeeRole(employeeId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-employees'] }),
  })

  return (
    <div className='admin-page'>
      <h2>管理工作台</h2>

      <section className='panel'>
        <h3>新增员工</h3>
        <div className='admin-page__create'>
          <input
            className='text-input'
            placeholder='用户名'
            value={form.username}
            onChange={(event) => setForm({ ...form, username: event.target.value })}
          />
          <input
            className='text-input'
            placeholder='姓名'
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
          <input
            className='text-input'
            type='password'
            placeholder='初始密码（至少 6 位）'
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
          />
          <input
            className='text-input'
            placeholder='电话（可选）'
            value={form.phone}
            onChange={(event) => setForm({ ...form, phone: event.target.value })}
          />
          <select
            className='select'
            value={form.role}
            onChange={(event) => setForm({ ...form, role: event.target.value as 'employee' | 'manager' })}
          >
            <option value='employee'>员工</option>
            <option value='manager'>店长</option>
          </select>
          <button
            type='button'
            className='primary-button'
            onClick={() => create.mutate({ ...form, phone: form.phone || undefined })}
            disabled={create.isPending || !form.username || !form.name || !form.password}
          >
            {create.isPending ? '创建中…' : '创建员工'}
          </button>
        </div>
        {createError ? <p className='admin-page__error'>{createError}</p> : null}
      </section>

      <section className='panel'>
        <h3>员工管理（{employees.data?.length ?? 0}）</h3>
        <ul className='admin-page__employees'>
          {(employees.data ?? []).map((item) => (
            <li key={item.id}>
              <span className={`badge badge--${item.role}`}>{item.role === 'manager' ? '店长' : '员工'}</span>
              <strong>{item.name}</strong>
              <span className='muted'>{item.username}</span>
              <button
                type='button'
                className='ghost-button'
                onClick={() => role.mutate({ employeeId: item.id, role: item.role === 'manager' ? 'employee' : 'manager' })}
              >
                切换为{item.role === 'manager' ? '员工' : '店长'}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className='panel'>
        <h3>客户管理（全量档案）</h3>
        <ul>
          {(customers.data ?? []).map((item) => (
            <li key={item.id}>
              {item.name} · 负责人 #{item.ownerId} · {item.lifecycleStage}
              <select
                className='select'
                defaultValue=''
                onChange={(event) => event.target.value && transfer.mutate({ customerId: item.id, toEmployeeId: Number(event.target.value) })}
              >
                <option value=''>移交给…</option>
                {(employees.data ?? []).filter((employee) => employee.id !== item.ownerId).map((employee) => (
                  <option key={employee.id} value={employee.id}>{employee.name}</option>
                ))}
              </select>
            </li>
          ))}
        </ul>
      </section>

      <section className='panel'>
        <h3>会话监控</h3>
        <ul>
          {(sessions.data ?? []).map((session) => (
            <li key={session.session_id}>
              会话 {session.session_id} · 客户 #{session.customer_id} · {session.turns.length} 条建议
              <ul>{session.turns.map((turn) => (
                <li key={turn.id}>
                  {turn.skill} · {turn.status} · 引用 {turn.citations.length} 条 · <Link to={`/monitor?run=${turn.run_id}`}>Monitor</Link>
                </li>
              ))}</ul>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
