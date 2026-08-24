import { Navigate, useLocation } from 'react-router-dom'
import type { PropsWithChildren } from 'react'
import { useAuth } from './auth'

/** 未登录访问受保护页面 → 重定向登录页。 */
export function RequireAuth({ children }: PropsWithChildren) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  if (!isAuthenticated) {
    return <Navigate to='/login' replace state={{ from: location }} />
  }
  return <>{children}</>
}

/** 非店长（manager）访问管理端/Monitor → 重定向工作台。 */
export function RequireManager({ children }: PropsWithChildren) {
  const { isManager } = useAuth()
  if (!isManager) {
    return <Navigate to='/' replace />
  }
  return <>{children}</>
}
