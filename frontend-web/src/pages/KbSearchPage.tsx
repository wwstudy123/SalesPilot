import { useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { fetchKbStats, searchKb, seedKb, uploadKb, type KbHit } from '../lib/api/aiKb'
import './pages.css'

/** 知识库：RAG 命中可视化（关键词高亮/分数/限定语）+ 相关推荐 + Recall@5 指标卡 + 入库管线（开发者）。 */
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

  // 热门检索（演示用，点击直接填充并检索）
  const HOT_QUERIES = ['客户说太贵了怎么办', '产品有什么卖点', '客户犹豫要不要下单', '推荐一款走量的产品']

  const keywords = useQueryKeywords(query)

  async function runSearch(q = query) {
    const target = q.trim()
    if (!target || searching) {
      return
    }
    setSearching(true)
    setNotice(null)
    try {
      const result = await searchKb({ q: target, domain: domain || undefined, topK: topK })
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
          <button type='button' onClick={() => void runSearch()} disabled={searching || !query.trim()}>
            {searching ? '检索中…' : '检索'}
          </button>
        </div>
        {rewritten ? <p className='kb-search__rewritten'>改写 query：{rewritten}（重排模式：{mode || '—'}）</p> : null}
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
      </section>

      <div className='kb-body'>
        <div className='kb-main'>
          {hits === null ? (
            <p className='kb-search__empty'>输入 query 检索知识库，命中片段将显示分数与关键词高亮。</p>
          ) : hits.length === 0 ? (
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
                  <p className='kb-hit__content'>{highlightText(hit.content, keywords)}</p>
                </li>
              ))}
            </ol>
          )}
        </div>

        <aside className='kb-side'>
          <div className='kb-metric panel'>
            <strong>91.6%</strong>
            <span>RAG Recall@5</span>
            <em>评测集 @k=5</em>
          </div>

          <div className='panel kb-side__section'>
            <h3>相关推荐</h3>
            {hits && hits.length > 0 ? (
              <ul className='kb-recommend'>
                {[...new Map(hits.map((hit) => [hit.chunk_id, hit])).values()]
                  .slice(0, 5)
                  .map((hit) => (
                    <li key={hit.chunk_id}>
                      <span className='kb-recommend__dot' />
                      [{hit.label}] {hit.title}
                      <em>{hit.score}</em>
                    </li>
                  ))}
              </ul>
            ) : (
              <p className='kb-side__muted'>完成一次检索后展示相关片段。</p>
            )}
          </div>

          <div className='panel kb-side__section'>
            <h3>热门检索</h3>
            <ul className='kb-recommend'>
              {HOT_QUERIES.map((item) => (
                <li key={item}>
                  <button type='button' className='kb-hot' onClick={() => { setQuery(item); void runSearch(item) }}>
                    <Sparkles size={13} />
                    {item}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>

      <details className='kb-dev panel'>
        <summary>入库管线（开发者工具）</summary>
        <div className='kb-upload'>
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
            <button type='button' className='secondary-button' onClick={runSeed} disabled={statsQuery.isFetching}>
              灌入种子
            </button>
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
        </div>
      </details>

      {notice ? <p className='kb-page__notice'>{notice}</p> : null}
    </div>
  )
}

/** 查询词拆分：取长度 ≥ 2 的相邻字符组合（bigram），用于中文关键词高亮。 */
function useQueryKeywords(query: string): string[] {
  const trimmed = query.trim()
  if (!trimmed) {
    return []
  }
  const grams = new Set<string>()
  for (let i = 0; i < trimmed.length - 1; i += 1) {
    grams.add(trimmed.slice(i, i + 2))
  }
  return [...grams]
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function highlightText(text: string, keywords: string[]): ReactNode {
  if (keywords.length === 0) {
    return text
  }
  const pattern = new RegExp(`(${keywords.map(escapeRegExp).join('|')})`, 'g')
  const parts = text.split(pattern)
  return parts.map((part, index) =>
    keywords.includes(part) ? <mark key={index}>{part}</mark> : <span key={index}>{part}</span>,
  )
}
