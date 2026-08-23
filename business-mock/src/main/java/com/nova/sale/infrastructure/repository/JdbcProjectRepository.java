package com.nova.sale.infrastructure.repository;

import com.nova.sale.domain.model.ProjectRecord;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.util.List;
import java.util.Optional;

@Repository
public class JdbcProjectRepository implements ProjectRepository {
    private static final RowMapper<ProjectRecord> ROW_MAPPER = (rs, rowNum) -> new ProjectRecord(
            rs.getString("project_id"),
            rs.getString("title"),
            rs.getString("premise"),
            rs.getString("style_code"),
            rs.getTimestamp("created_at").toInstant(),
            rs.getTimestamp("updated_at").toInstant()
    );

    private final JdbcTemplate jdbcTemplate;

    public JdbcProjectRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public ProjectRecord save(ProjectRecord project) {
        jdbcTemplate.update("""
                INSERT INTO project (project_id, title, premise, style_code, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (project_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    premise = EXCLUDED.premise,
                    style_code = EXCLUDED.style_code,
                    updated_at = EXCLUDED.updated_at
                """,
                project.projectId(),
                project.title(),
                project.premise(),
                project.style(),
                Timestamp.from(project.createdAt()),
                Timestamp.from(project.updatedAt())
        );
        return project;
    }

    @Override
    public Optional<ProjectRecord> findById(String projectId) {
        List<ProjectRecord> rows = jdbcTemplate.query(
                "SELECT project_id, title, premise, style_code, created_at, updated_at FROM project WHERE project_id = ?",
                ROW_MAPPER,
                projectId
        );
        return rows.stream().findFirst();
    }

    @Override
    public List<ProjectRecord> findAll() {
        return jdbcTemplate.query(
                "SELECT project_id, title, premise, style_code, created_at, updated_at FROM project ORDER BY created_at",
                ROW_MAPPER
        );
    }

    @Override
    public boolean deleteById(String projectId) {
        return jdbcTemplate.update("DELETE FROM project WHERE project_id = ?", projectId) > 0;
    }
}
