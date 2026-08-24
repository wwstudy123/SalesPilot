import { createContext, useContext, useState, type PropsWithChildren } from 'react'
import { login as apiLogin, logout as apiLogout } from '../lib/api/customers'
import type { Employee } from '../lib/types/api'

const USER_KEY = 'sale_user'

type AuthContextValue = {
  user: Employee | null
  isAuthenticated: boolean
  isManager: boolean
  signIn: (username: string, password: string) => Promise<void>
  signOut: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function readStoredUser(): Employee | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as Employee) : null
  } catch {
    return null
  }
}

/** 认证上下文：维护登录用户与角色（普通员工 / 店长 manager）。 */
export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<Employee | null>(readStoredUser)

  const signIn = async (username: string, password: string) => {
    const result = await apiLogin(username, password)
    const nextUser: Employee = {
      id: result.employeeId,
      username,
      name: result.name,
      role: result.role,
      phone: null,
    }
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser))
    setUser(nextUser)
  }

  const signOut = () => {
    apiLogout()
    localStorage.removeItem(USER_KEY)
    setUser(null)
  }

  const value: AuthContextValue = {
    user,
    isAuthenticated: user !== null,
    isManager: user?.role === 'manager',
    signIn,
    signOut,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
