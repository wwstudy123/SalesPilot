package com.acme.platform.infrastructure.repository;

import com.acme.platform.domain.model.ProjectRecord;

import java.util.List;
import java.util.Optional;

public interface ProjectRepository {
    ProjectRecord save(ProjectRecord project);

    Optional<ProjectRecord> findById(String projectId);

    List<ProjectRecord> findAll();

    boolean deleteById(String projectId);
}
