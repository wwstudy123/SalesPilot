import React from 'react'
import ReactDOM from 'react-dom/client'
import { AppProviders } from '../../app/providers'
import { AppRouter } from '../../app/router'
import '../../styles/theme.css'
import '../../styles/globals.css'

// sale_sidebar 员工端入口（M4 起承载：对话工作台/我的客户/客户详情/我的日程）
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppProviders>
      <AppRouter />
    </AppProviders>
  </React.StrictMode>,
)
