import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchCustomers, fetchEmployees, transferCustomer, updateEmployeeRole } from '../lib/api/admin'
import { fetchAdminSessions } from '../lib/api/admin'
import './pages.css'

/** M7 管理端最小工作台：员工、全量客户与会话采纳监控。 */
export function AdminPage() {
  const queryClient = useQueryClient()
  const employees = useQuery({ queryKey: ['admin-employees'], queryFn: fetchEmployees })
  const customers = useQuery({ queryKey: ['admin-customers'], queryFn: fetchCustomers })
  const sessions = useQuery({ queryKey: ['admin-sessions'], queryFn: fetchAdminSessions })
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
        <h3>员工管理</h3>
        <ul>{(employees.data ?? []).map((item) => (
          <li key={item.id}>
            {item.name} · {item.role}
            <button onClick={() => role.mutate({ employeeId: item.id, role: item.role === 'manager' ? 'employee' : 'manager' })}>
              切换为{item.role === 'manager' ? '员工' : '管理员'}
            </button>
          </li>
        ))}</ul>
      </section>
      <section className='panel'>
        <h3>客户管理（全量档案）</h3>
        <ul>{(customers.data ?? []).map((item) => (
          <li key={item.id}>
            {item.name} · 负责人 #{item.ownerId} · {item.lifecycleStage}
            <select defaultValue='' onChange={(event) => event.target.value && transfer.mutate({ customerId: item.id, toEmployeeId: Number(event.target.value) })}>
              <option value=''>移交给…</option>
              {(employees.data ?? []).filter((employee) => employee.id !== item.ownerId).map((employee) => (
                <option key={employee.id} value={employee.id}>{employee.name}</option>
              ))}
            </select>
          </li>
        ))}</ul>
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
