import { useLocation } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { useAuth } from '../../app/auth'
import './layout.css'

const PAGE_META: Array<{ prefix: string; title: string; subtitle: string }> = [
  { prefix: '/customers', title: '我的客户', subtitle: '客户全览、跟进记录与分层标签' },
  { prefix: '/chat', title: 'AI 助手', subtitle: '意图路由 · 工具调用 · RAG 引用的销售 Copilot' },
  { prefix: '/kb', title: '知识库', subtitle: 'RAG 检索命中可视化与入库管线' },
  { prefix: '/admin', title: '管理端', subtitle: '员工与客户管理' },
  { prefix: '/monitor', title: 'Monitor', subtitle: '运行时监控与调用审计' },
  { prefix: '/', title: '工作台', subtitle: '今日重点客户与快捷操作，一屏掌握' },
]

/** 全局顶部栏：页面标题 + 副标题 + 通知铃铛 + 用户头像。 */
export function TopBar() {
  const location = useLocation()
  const { user } = useAuth()
  const meta = PAGE_META.find((item) => location.pathname.startsWith(item.prefix)) ?? PAGE_META[PAGE_META.length - 1]

  return (
    <header className='topbar'>
      <div className='topbar__title'>
        <h1>{meta.title}</h1>
        <p>{meta.subtitle}</p>
      </div>
      <div className='topbar__actions'>
        <button type='button' className='topbar__bell' title='暂无新通知' aria-label='通知'>
          <Bell size={18} strokeWidth={1.8} />
        </button>
        <span className='topbar__avatar'>{user?.name.slice(0, 1) ?? 'U'}</span>
      </div>
    </header>
  )
}
