import { ArrowRight, Blocks, BookOpen, Layers, Rocket, Sparkles, Workflow } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import './pages.css'

const features = [
  {
    icon: Workflow,
    title: 'LangGraph 流水线',
    description: '内置 load → generate → commit → checkpoint 最小流水线，可平滑扩展为复杂 Agent 编排。',
  },
  {
    icon: Blocks,
    title: '三端分层',
    description: 'React 前端、Spring Boot 平台层与 Python Runtime 通过代理分流，职责清晰。',
  },
  {
    icon: Layers,
    title: 'DDD 结构',
    description: 'Java 层 interfaces/application/domain/infrastructure 四层 + Flyway 迁移开箱即用。',
  },
  {
    icon: BookOpen,
    title: '文件持久化',
    description: 'Run 产物按 sections/summaries/meta 目录组织，支持 checkpoint 与断点续跑。',
  },
  {
    icon: Rocket,
    title: 'SSE 事件流',
    description: 'Internal API 提供 SSE 事件订阅与进度快照，前端可实时展示运行状态。',
  },
  {
    icon: Sparkles,
    title: '示例实体',
    description: '以 Project 为示例贯穿三端 CRUD，替换为你的领域实体即可快速起步。',
  },
]

export function HomePage() {
  const navigate = useNavigate()

  return (
    <div className='home-page'>
      <section className='home-hero'>
        <div className='home-section__inner home-page__content'>
          <div className='hero-copy'>
            <div className='hero-copy__eyebrow'>
              <Sparkles size={14} />
              通用 Agent 项目骨架
            </div>

            <h1 className='hero-title'>
              <span>三端一体的</span>
              <span className='hero-title__accent'>AI 应用脚手架</span>
            </h1>

            <p>
              React + Spring Boot + Python Runtime 的最小可运行闭环：保留编排、事件流与持久化等横切能力，
              领域逻辑以 Project 示例贯穿，替换成你的业务即可起步。
            </p>

            <div className='hero-copy__actions'>
              <button type='button' className='primary-button hero-copy__button' onClick={() => navigate('/projects')}>
                <Rocket size={18} />
                查看示例项目
                <ArrowRight size={16} />
              </button>
            </div>

            <div className='hero-copy__highlights'>
              <span>最小闭环</span>
              <span>可编译可启动可测试</span>
              <span>中性命名</span>
            </div>
          </div>
        </div>
      </section>

      <section className='home-features'>
        <div className='home-section__inner'>
          <div className='home-section__heading'>
            <h2 className='home-section__title'>
              骨架里<span className='hero-title__accent'>有什么</span>
            </h2>
            <p>横切能力保留，领域逻辑最小化，按需生长</p>
          </div>

          <div className='features-grid'>
            {features.map((feature) => {
              const Icon = feature.icon
              return (
                <article key={feature.title} className='feature-card panel'>
                  <div className='feature-card__icon'>
                    <Icon size={24} />
                  </div>
                  <h3>{feature.title}</h3>
                  <p>{feature.description}</p>
                </article>
              )
            })}
          </div>
        </div>
      </section>

      <footer className='home-footer'>
        <div className='home-footer__inner'>
          <div className='home-footer__brand'>
            Agent<span className='hero-title__accent'>Kit</span>
          </div>
          <p>AgentKit Skeleton · 通用三端项目骨架</p>
        </div>
      </footer>
    </div>
  )
}
