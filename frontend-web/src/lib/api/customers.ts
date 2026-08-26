import { apiFetch } from './client'
import type { Customer, CustomerTag, Employee, FollowUp, LoginResult, ProfileField, Purchase } from '../types/api'

const TOKEN_KEY = 'sale_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

function authedFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  return apiFetch<T>(path, {
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  })
}

export async function login(username: string, password: string) {
  const result = await apiFetch<LoginResult>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  setToken(result.token)
  return result
}

export function logout() {
  setToken(null)
}

export async function fetchMe() {
  return authedFetch<Employee>('/api/v1/employees/me')
}

export async function fetchCustomers() {
  return authedFetch<Customer[]>('/api/v1/customers')
}

export async function createCustomer(input: {
  name: string
  phone?: string
  gender?: 'M' | 'F' | 'U'
  lifecycleStage?: 'new' | 'prospective' | 'existing' | 'churn_risk'
  source?: string
  remark?: string
}) {
  return authedFetch<Customer>('/api/v1/customers', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function fetchCustomer(customerId: number) {
  return authedFetch<Customer>(`/api/v1/customers/${customerId}`)
}

export async function fetchFollowUps(customerId: number) {
  return authedFetch<FollowUp[]>(`/api/v1/customers/${customerId}/follow-ups`)
}

export async function fetchPurchases(customerId: number) {
  return authedFetch<Purchase[]>(`/api/v1/customers/${customerId}/purchases`)
}

export async function fetchProfileFields(customerId: number) {
  return authedFetch<ProfileField[]>(`/api/v1/customers/${customerId}/profile`)
}

export async function fetchCustomerTags(customerId: number) {
  return authedFetch<CustomerTag[]>(`/api/v1/customers/${customerId}/tags`)
}
