import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { ChatPage } from '../pages/ChatPage'
import { AdminPage } from '../pages/AdminPage'
import { CustomerDetailPage } from '../pages/CustomerDetailPage'
import { CustomersPage } from '../pages/CustomersPage'
import { HomePage } from '../pages/HomePage'
import { KbSearchPage } from '../pages/KbSearchPage'
import { LoginPage } from '../pages/LoginPage'
import { MonitorPage } from '../pages/MonitorPage'
import { RequireAuth, RequireManager } from './guards'

const router = createBrowserRouter([
  // 登录页独立于工作台外壳
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <HomePage /> },
      { path: 'customers', element: <CustomersPage /> },
      { path: 'customers/:customerId', element: <CustomerDetailPage /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'kb', element: <KbSearchPage /> },
      {
        path: 'admin',
        element: (
          <RequireManager>
            <AdminPage />
          </RequireManager>
        ),
      },
      {
        path: 'monitor',
        element: (
          <RequireManager>
            <MonitorPage />
          </RequireManager>
        ),
      },
      { path: '*', element: <Navigate to='/' replace /> },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
