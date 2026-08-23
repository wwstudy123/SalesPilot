package com.nova.sagt.application;

import com.nova.sagt.domain.model.ProjectRecord;
import com.nova.sagt.infrastructure.repository.ProjectRepository;
import com.nova.sagt.interfaces.dto.CreateProjectRequest;
import com.nova.sagt.interfaces.dto.ProjectListResponse;
import com.nova.sagt.interfaces.dto.ProjectResponse;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Comparator;
import java.util.List;

@Service
public class ProjectApplicationService {
    private final ProjectRepository repository;

    public ProjectApplicationService(ProjectRepository repository) {
        this.repository = repository;
    }

    public ProjectResponse getProject(String projectId) {
        ProjectRecord project = repository.findById(projectId)
                .orElseThrow(() -> new IllegalArgumentException("project not found: " + projectId));
        return toResponse(project);
    }

    public ProjectListResponse listProjects() {
        List<ProjectResponse> items = repository.findAll().stream()
                .sorted(Comparator.comparing(ProjectRecord::createdAt))
                .map(this::toResponse)
                .toList();
        return new ProjectListResponse(items);
    }

    public ProjectResponse createProject(CreateProjectRequest request) {
        Instant now = Instant.now();
        ProjectRecord project = new ProjectRecord(
                request.projectId().trim(),
                request.title().trim(),
                request.premise() == null ? "" : request.premise().trim(),
                request.style() == null || request.style().isBlank() ? "default" : request.style().trim(),
                now,
                now
        );
        return toResponse(repository.save(project));
    }

    public ProjectResponse deleteProject(String projectId) {
        ProjectResponse response = getProject(projectId);
        repository.deleteById(projectId);
        return response;
    }

    private ProjectResponse toResponse(ProjectRecord project) {
        return new ProjectResponse(
                project.projectId(),
                project.title(),
                project.premise(),
                project.style(),
                project.createdAt().toString(),
                project.updatedAt().toString()
        );
    }
}
