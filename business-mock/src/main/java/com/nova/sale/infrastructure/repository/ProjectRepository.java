package com.nova.sale.infrastructure.repository;

import com.nova.sale.domain.model.ProjectRecord;

import java.util.List;
import java.util.Optional;

public interface ProjectRepository {
    ProjectRecord save(ProjectRecord project);

    Optional<ProjectRecord> findById(String projectId);

    List<ProjectRecord> findAll();

    boolean deleteById(String projectId);
}
