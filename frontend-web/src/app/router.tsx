import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { ChatPage } from '../pages/ChatPage'
import { CustomerDetailPage } from '../pages/CustomerDetailPage'
import { CustomersPage } from '../pages/CustomersPage'
import { HomePage } from '../pages/HomePage'
import { KbSearchPage } from '../pages/KbSearchPage'
import { LoginPage } from '../pages/LoginPage'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'customers', element: <CustomersPage /> },
      { path: 'customers/:customerId', element: <CustomerDetailPage /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'kb', element: <KbSearchPage /> },
      { path: '*', element: <Navigate to='/' replace /> },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
