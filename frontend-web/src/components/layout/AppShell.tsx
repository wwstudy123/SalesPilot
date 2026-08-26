import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import './layout.css'

/** Copilot 工作台 Shell：左侧边栏 + 顶部栏 + 全宽内容区。 */
export function AppShell() {
  return (
    <div className='app-shell'>
      <Sidebar />
      <main className='app-shell__main'>
        <TopBar />
        <div className='app-shell__content'>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
