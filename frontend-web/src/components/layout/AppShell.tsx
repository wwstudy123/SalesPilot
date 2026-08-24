import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import './layout.css'

/** Copilot 工作台 Shell：左侧边栏 + 全宽内容区。 */
export function AppShell() {
  return (
    <div className='app-shell'>
      <Sidebar />
      <main className='app-shell__main'>
        <Outlet />
      </main>
    </div>
  )
}
