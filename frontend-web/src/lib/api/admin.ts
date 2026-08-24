import { apiFetch } from './client'
import { getToken } from './customers'
import type { Customer, Employee } from '../types/api'

function adminFetch<T>(path: string): Promise<T> {
  const token = getToken()
  return apiFetch<T>(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
}

function adminWrite<T>(path: string, body: unknown): Promise<T> {
  const token = getToken()
  return apiFetch<T>(path, {
    method: 'PUT',
    body: JSON.stringify(body),
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
}

export function fetchEmployees() {
  return adminFetch<Employee[]>('/api/v1/employees')
}

export function fetchCustomers() {
  return adminFetch<Customer[]>('/api/v1/customers')
}

export function transferCustomer(customerId: number, toEmployeeId: number) {
  return adminWrite<Customer>(`/api/v1/customers/${customerId}/transfer`, { toEmployeeId })
}

export function updateEmployeeRole(employeeId: number, role: 'employee' | 'manager') {
  return adminWrite<Employee>(`/api/v1/employees/${employeeId}/role`, { role })
}

export type AdminSession = {
  session_id: string
  employee_id: number
  customer_id: number
  latest_at: string
  turns: Array<{ id: number; skill: string; status: string; citations: unknown[] }>
}

export function fetchAdminSessions() {
  return adminFetch<AdminSession[]>('/api/ai/admin/sessions')
}
