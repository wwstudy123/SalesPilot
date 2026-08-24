package com.nova.sale.infrastructure.repository;

import com.nova.sale.domain.model.Employee;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public class EmployeeRepository {
    private static final String COLUMNS = "id, username, password_hash, name, role, phone, created_at, updated_at";

    private static final RowMapper<Employee> ROW_MAPPER = (rs, rowNum) -> new Employee(
            rs.getLong("id"),
            rs.getString("username"),
            rs.getString("password_hash"),
            rs.getString("name"),
            rs.getString("role"),
            rs.getString("phone"),
            rs.getTimestamp("created_at").toInstant(),
            rs.getTimestamp("updated_at").toInstant()
    );

    private final JdbcTemplate jdbcTemplate;

    public EmployeeRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Optional<Employee> findByUsername(String username) {
        List<Employee> rows = jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM employee WHERE username = ? AND deleted_token = '0'",
                ROW_MAPPER,
                username
        );
        return rows.stream().findFirst();
    }

    public Optional<Employee> findById(Long id) {
        List<Employee> rows = jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM employee WHERE id = ? AND deleted_token = '0'",
                ROW_MAPPER,
                id
        );
        return rows.stream().findFirst();
    }

    public List<Employee> findAll() {
        return jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM employee WHERE deleted_token = '0' ORDER BY id",
                ROW_MAPPER
        );
    }

    public void updateRole(Long employeeId, String role) {
        jdbcTemplate.update(
                "UPDATE employee SET role = ?, updated_at = CURRENT_TIMESTAMP(3) WHERE id = ? AND deleted_token = '0'",
                role, employeeId
        );
    }
}
