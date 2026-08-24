import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { fetchMonitorRun, fetchMonitorRuns } from '../lib/api/admin'
import './pages.css'

function duration(startedAt: string, finishedAt: string | null): string {
  if (!finishedAt) return '运行中'
  return `${Math.max(0, new Date(finishedAt).getTime() - new Date(startedAt).getTime())} ms`
}

/** M8 简版 Monitor：Run 筛选与可展开 Span 瀑布。 */
export function MonitorPage() {
  const [searchParams] = useSearchParams()
  const [intent, setIntent] = useState('')
  const [status, setStatus] = useState('')
  const [selectedRunId, setSelectedRunId] = useState<string | null>(() => searchParams.get('run'))
  const runs = useQuery({ queryKey: ['monitor-runs', intent, status], queryFn: () => fetchMonitorRuns({ intent, status }) })
  const detail = useQuery({ queryKey: ['monitor-run', selectedRunId], queryFn: () => fetchMonitorRun(selectedRunId!), enabled: Boolean(selectedRunId) })

  return (
    <div className='monitor-page'>
      <h2>Monitor</h2>
      <section className='panel'>
        <label>
          意图
          <input value={intent} placeholder='例如 talk_script' onChange={(event) => setIntent(event.target.value)} />
        </label>
        <label>
          状态
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value=''>全部</option>
            <option value='completed'>完成</option>
            <option value='failed'>失败</option>
          </select>
        </label>
      </section>
      <section className='panel'>
        <h3>Run 列表</h3>
        <ul>
          {(runs.data ?? []).map((run) => (
            <li key={run.run_id}>
              <button className='secondary-button' onClick={() => setSelectedRunId(run.run_id)}>
                查看
              </button>{' '}
              {run.intent ?? '-'} · {run.status} · {duration(run.started_at, run.finished_at)} · {run.run_id}
            </li>
          ))}
        </ul>
      </section>
      {detail.data ? (
        <section className='panel'>
          <h3>Span 时间线：{detail.data.run.run_id}</h3>
          <ol className='monitor-page__timeline'>
            {detail.data.spans.map((span) => (
              <li key={span.span_id}>
                <strong>{span.name}</strong> · {span.status} · {duration(span.started_at, span.finished_at)}
                {span.detail ? <pre>{span.detail}</pre> : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  )
}
