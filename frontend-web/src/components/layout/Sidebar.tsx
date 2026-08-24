import { useLocation, useNavigate } from 'react-router-dom'
import { BookOpen, LayoutDashboard, MessageSquare, ShieldCheck, Users, Activity, LogIn } from 'lucide-react'
import './layout.css'

type NavItem = {
  to: string
  label: string
  icon: typeof LayoutDashboard
  isActive: (pathname: string) => boolean
}

const primaryNav: NavItem[] = [
  { to: '/', label: '工作台', icon: LayoutDashboard, isActive: (p) => p === '/' },
  { to: '/customers', label: '我的客户', icon: Users, isActive: (p) => p.startsWith('/customers') },
  { to: '/chat', label: 'AI 助手', icon: MessageSquare, isActive: (p) => p.startsWith('/chat') },
  { to: '/kb', label: '知识库', icon: BookOpen, isActive: (p) => p.startsWith('/kb') },
]

const adminNav: NavItem[] = [
  { to: '/admin', label: '管理端', icon: ShieldCheck, isActive: (p) => p.startsWith('/admin') },
  { to: '/monitor', label: 'Monitor', icon: Activity, isActive: (p) => p.startsWith('/monitor') },
]

/** 左侧边栏（Copilot 工作台布局）：主导航 + 管理区分组 + 底部登录。 */
export function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  function renderGroup(items: NavItem[]) {
    return items.map((item) => {
      const Icon = item.icon
      const active = item.isActive(location.pathname)
      return (
        <button
          key={item.to}
          type='button'
          className={`sidebar__item ${active ? 'is-active' : ''}`}
          onClick={() => navigate(item.to)}
        >
          <Icon size={17} strokeWidth={active ? 2.2 : 1.8} />
          <span>{item.label}</span>
        </button>
      )
    })
  }

  return (
    <aside className='sidebar'>
      <button className='sidebar__brand' onClick={() => navigate('/')}>
        <span className='sidebar__logo'>S</span>
        <span className='sidebar__brand-text'>
          Sales<span className='sidebar__brand-accent'>Pilot</span>
        </span>
      </button>

      <nav className='sidebar__nav'>
        <div className='sidebar__group'>{renderGroup(primaryNav)}</div>
        <div className='sidebar__group-label'>管理</div>
        <div className='sidebar__group'>{renderGroup(adminNav)}</div>
      </nav>

      <div className='sidebar__footer'>
        <button type='button' className='sidebar__item' onClick={() => navigate('/login')}>
          <LogIn size={17} strokeWidth={1.8} />
          <span>登录</span>
        </button>
      </div>
    </aside>
  )
}
