import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { createProject, deleteProject, fetchProjects } from '../lib/api/projects'
import { formatDate } from '../lib/utils/format'
import './pages.css'

export function ProjectsPage() {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [premise, setPremise] = useState('')
  const [error, setError] = useState<string | null>(null)

  const projectsQuery = useQuery({ queryKey: ['projects'], queryFn: fetchProjects })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['projects'] })

  const createMutation = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      setTitle('')
      setPremise('')
      setError(null)
      invalidate()
    },
    onError: (err: Error) => setError(err.message),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: invalidate,
    onError: (err: Error) => setError(err.message),
  })

  const handleCreate = () => {
    if (!title.trim()) {
      setError('请填写项目标题')
      return
    }
    const projectId = `proj-${Date.now().toString(36)}`
    createMutation.mutate({ projectId, title: title.trim(), premise: premise.trim() })
  }

  const projects = projectsQuery.data ?? []

  return (
    <div className='projects-page'>
      <section className='projects-page__create panel'>
        <h2>新建示例项目</h2>
        <input
          className='text-input'
          placeholder='项目标题'
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <textarea
          className='text-input'
          placeholder='项目描述（可选）'
          rows={3}
          value={premise}
          onChange={(event) => setPremise(event.target.value)}
        />
        {error ? <p className='projects-page__error'>{error}</p> : null}
        <button type='button' className='primary-button' onClick={handleCreate} disabled={createMutation.isPending}>
          <Plus size={16} />
          创建项目
        </button>
      </section>

      <section className='projects-page__list'>
        <h2>项目列表</h2>
        {projectsQuery.isLoading ? <p>加载中…</p> : null}
        {projectsQuery.isError ? <p>加载失败：{(projectsQuery.error as Error).message}</p> : null}
        {!projectsQuery.isLoading && projects.length === 0 ? <p>暂无项目，先创建一个吧。</p> : null}
        <ul>
          {projects.map((project) => (
            <li key={project.projectId} className='projects-page__item panel'>
              <div>
                <strong>{project.title}</strong>
                <p>{project.premise || '（无描述）'}</p>
                <span>{formatDate(project.createdAt)}</span>
              </div>
              <button
                type='button'
                className='secondary-button'
                onClick={() => deleteMutation.mutate(project.projectId)}
                disabled={deleteMutation.isPending}
              >
                <Trash2 size={16} />
                删除
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
