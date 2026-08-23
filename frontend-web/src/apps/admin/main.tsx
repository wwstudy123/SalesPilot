import React from 'react'
import ReactDOM from 'react-dom/client'
import { AppProviders } from '../../app/providers'
import { AppRouter } from '../../app/router'
import '../../styles/theme.css'
import '../../styles/globals.css'

// sale_admin 管理端入口（M7 起承载：概览/员工管理/客户管理/会话监控/Monitor/评测中心）
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppProviders>
      <AppRouter />
    </AppProviders>
  </React.StrictMode>,
)
