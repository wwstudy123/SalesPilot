import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { CustomerDetailPage } from '../pages/CustomerDetailPage'
import { CustomersPage } from '../pages/CustomersPage'
import { HomePage } from '../pages/HomePage'
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
      { path: '*', element: <Navigate to='/' replace /> },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
