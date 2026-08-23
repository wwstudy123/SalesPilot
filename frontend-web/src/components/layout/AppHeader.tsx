import { useLocation, useNavigate } from 'react-router-dom'

const navItems = [
  {
    to: '/',
    label: '首页',
    isActive: (pathname: string) => pathname === '/',
  },
  {
    to: '/projects',
    label: '项目列表',
    isActive: (pathname: string) => pathname.startsWith('/projects'),
  },
]

export function AppHeader() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <header className='app-header'>
      <button className='brand' onClick={() => navigate('/')}>
        <span className='brand__logo'>✦</span>
        <span className='brand__text'>Agent<span className='brand__text-accent'>Kit</span></span>
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
