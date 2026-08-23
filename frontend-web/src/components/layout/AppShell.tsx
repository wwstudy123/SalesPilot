import { Outlet } from 'react-router-dom'
import { AppHeader } from './AppHeader'
import './layout.css'

export function AppShell() {
  return (
    <div className='app-shell'>
      <AppHeader />
      <main className='app-shell__main'>
        <Outlet />
      </main>
    </div>
  )
}
