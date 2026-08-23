package com.acme.platform.infrastructure.repository;

import com.acme.platform.domain.model.ProjectRecord;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

public class InMemoryProjectRepository implements ProjectRepository {
    private final Map<String, ProjectRecord> projects = new ConcurrentHashMap<>();

    @Override
    public ProjectRecord save(ProjectRecord project) {
        projects.put(project.projectId(), project);
        return project;
    }

    @Override
    public Optional<ProjectRecord> findById(String projectId) {
        return Optional.ofNullable(projects.get(projectId));
    }

    @Override
    public List<ProjectRecord> findAll() {
        return List.copyOf(projects.values());
    }

    @Override
    public boolean deleteById(String projectId) {
        return projects.remove(projectId) != null;
    }
}
