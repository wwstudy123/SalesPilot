import { useLocation, useNavigate } from 'react-router-dom'

const navItems = [
  {
    to: '/',
    label: '首页',
    isActive: (pathname: string) => pathname === '/',
  },
  {
    to: '/customers',
    label: '我的客户',
    isActive: (pathname: string) => pathname.startsWith('/customers'),
  },
  {
    to: '/chat',
    label: 'AI 话术助手',
    isActive: (pathname: string) => pathname.startsWith('/chat'),
  },
  {
    to: '/kb',
    label: '知识库',
    isActive: (pathname: string) => pathname.startsWith('/kb'),
  },
  {
    to: '/login',
    label: '登录',
    isActive: (pathname: string) => pathname.startsWith('/login'),
  },
]

export function AppHeader() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <header className='app-header'>
      <button className='brand' onClick={() => navigate('/')}>
        <span className='brand__logo'>✦</span>
        <span className='brand__text'>Sales<span className='brand__text-accent'>Pilot</span></span>
      </button>

      <nav className='app-header__nav'>
        {navItems.map((item) => (
          <button
            key={item.label}
            type='button'
            className={`app-header__link ${item.isActive(location.pathname) ? 'is-active' : ''}`}
            onClick={() => navigate(item.to)}
          >
            {item.label}
          </button>
        ))}
      </nav>
    </header>
  )
}
