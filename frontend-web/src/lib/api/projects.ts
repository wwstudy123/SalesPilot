import { apiFetch } from './client'
import type { CreateProjectRequest, Project, ProjectListResponse } from '../types/api'

export async function fetchProjects() {
  const data = await apiFetch<ProjectListResponse>('/api/v1/projects')
  return data.items
}

export async function fetchProject(projectId: string) {
  return apiFetch<Project>(`/api/v1/projects/${projectId}`)
}

export async function createProject(payload: CreateProjectRequest) {
  return apiFetch<Project>('/api/v1/projects', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteProject(projectId: string) {
  return apiFetch<Project>(`/api/v1/projects/${projectId}`, {
    method: 'DELETE',
  })
}
