import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchKbStats, searchKb, seedKb, uploadKb, type KbHit } from '../lib/api/aiKb'
import './pages.css'

/** M5 检索测试页：RAG 命中可视化 + 知识库入库（上传/灌种）+ 后端模式展示。 */
export function KbSearchPage() {
  const statsQuery = useQuery({ queryKey: ['kb-stats'], queryFn: fetchKbStats, refetchOnMount: true })
  const [query, setQuery] = useState('客户说太贵了怎么办')
  const [domain, setDomain] = useState<'' | 'playbook' | 'product'>('')
  const [topK, setTopK] = useState(5)
  const [hits, setHits] = useState<KbHit[] | null>(null)
  const [mode, setMode] = useState<string>('')
  const [rewritten, setRewritten] = useState('')
  const [searching, setSearching] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  // 上传表单
  const [upDomain, setUpDomain] = useState<'playbook' | 'product'>('playbook')
  const [upTitle, setUpTitle] = useState('')
  const [upText, setUpText] = useState('')
  const [uploading, setUploading] = useState(false)

  async function runSearch() {
    if (!query.trim() || searching) {
      return
    }
    setSearching(true)
    setNotice(null)
    try {
      const result = await searchKb({ q: query.trim(), domain: domain || undefined, topK: topK })
      setHits(result.hits)
      setMode(result.mode)
      setRewritten(result.rewritten)
    } catch (error) {
      setNotice((error as Error).message)
      setHits([])
    } finally {
      setSearching(false)
    }
  }

  async function runSeed() {
    setNotice(null)
    try {
      await seedKb()
      await statsQuery.refetch()
      setNotice('种子已灌入并原子发布')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function runUpload() {
    if (!upTitle.trim() || !upText.trim() || uploading) {
      return
    }
    setUploading(true)
    setNotice(null)
    try {
      const texts = upText.split(/\n{2,|\n/).map((line) => line.trim()).filter(Boolean)
      const result = await uploadKb({ domain: upDomain, title: upTitle.trim(), texts })
      await statsQuery.refetch()
      setNotice(
        `已上传：${result.ingested.chunk_count} 切片（v${result.ingested.version}），${result.ready ? '已原子发布' : 'staging 未发布'}`,
      )
      setUpTitle('')
      setUpText('')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setUploading(false)
    }
  }

  const stats = statsQuery.data

  return (
    <div className='kb-page'>
      <section className='kb-page__header'>
        <h1>知识库检索测试</h1>
        <p>M5 入库管线：上传 → 切片 → 向量化 → 原子切换 ready；RAG 命中可视化（角标 / 分数 / 限定语）。</p>
      </section>

      <section className='kb-stats'>
        <div>
          <span>ready 切片</span>
          <strong>{stats?.ready_chunks ?? '—'}</strong>
        </div>
        <div>
          <span>向量后端</span>
          <strong>{stats?.vector_backend === 'milvus' ? 'Milvus' : 'lite'}</strong>
        </div>
        {stats?.docs.map((row) => (
          <div key={`${row.domain}-${row.status}`}>
            <span>
              {row.domain} / {row.status}
            </span>
            <strong>{row.count}</strong>
          </div>
        ))}
        <button type='button' className='secondary-button' onClick={runSeed} disabled={statsQuery.isFetching}>
          灌入种子
        </button>
      </section>

      <section className='kb-search'>
        <div className='kb-search__row'>
          <input
            value={query}
            placeholder='检索 query，例如：客户嫌太贵'
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                void runSearch()
              }
            }}
            disabled={searching}
          />
          <select value={domain} onChange={(event) => setDomain(event.target.value as typeof domain)} disabled={searching}>
            <option value=''>全部集合</option>
            <option value='playbook'>playbook</option>
            <option value='product'>product</option>
          </select>
          <input
            type='number'
            min={1}
            max={10}
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value) || 5)}
            disabled={searching}
            style={{ width: 64 }}
          />
          <button type='button' onClick={runSearch} disabled={searching || !query.trim()}>
            {searching ? '检索中…' : '检索'}
          </button>
        </div>
        {rewritten ? <p className='kb-search__rewritten'>改写 query：{rewritten}（重排模式：{mode || '—'}）</p> : null}

        {hits === null ? null : hits.length === 0 ? (
          <p className='kb-search__empty'>无命中（阈值 &lt;0.25 已剔除；低于 0.60 会附限定语）</p>
        ) : (
          <ol className='kb-hits'>
            {hits.map((hit) => (
              <li key={hit.chunk_id} className={`kb-hit${hit.hedge ? ' kb-hit--hedge' : ''}`}>
                <div className='kb-hit__head'>
                  <span className='kb-hit__label'>[{hit.label}]</span>
                  <span className='kb-hit__title'>{hit.title}</span>
                  <span className='kb-hit__score'>score {hit.score}</span>
                  {hit.hedge ? <span className='kb-hit__hedge'>限定语</span> : null}
                </div>
                <p className='kb-hit__content'>{hit.content}</p>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className='kb-upload'>
        <h3>上传文档（入库管线）</h3>
        <div className='kb-upload__row'>
          <select value={upDomain} onChange={(event) => setUpDomain(event.target.value as typeof upDomain)}>
            <option value='playbook'>playbook（话术）</option>
            <option value='product'>product（产品）</option>
          </select>
          <input
            value={upTitle}
            placeholder='文档标题（场景名 / 产品名）'
            onChange={(event) => setUpTitle(event.target.value)}
            disabled={uploading}
          />
        </div>
        <textarea
          value={upText}
          placeholder='正文（多个段落用空行分隔，入库管线按段落/句号切片）'
          rows={4}
          onChange={(event) => setUpText(event.target.value)}
          disabled={uploading}
        />
        <button type='button' onClick={runUpload} disabled={uploading || !upTitle.trim() || !upText.trim()}>
          {uploading ? '上传中…' : '上传并发布'}
        </button>
      </section>

      {notice ? <p className='kb-page__notice'>{notice}</p> : null}
    </div>
  )
}
