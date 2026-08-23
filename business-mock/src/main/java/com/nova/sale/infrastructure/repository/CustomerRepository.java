package com.nova.sale.infrastructure.repository;

import com.nova.sale.domain.model.Customer;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

@Repository
public class CustomerRepository {
    private static final String COLUMNS =
            "id, owner_id, name, phone, gender, lifecycle_stage, source, remark, created_at, updated_at";

    private static final RowMapper<Customer> ROW_MAPPER = (rs, rowNum) -> new Customer(
            rs.getLong("id"),
            rs.getLong("owner_id"),
            rs.getString("name"),
            rs.getString("phone"),
            rs.getString("gender"),
            rs.getString("lifecycle_stage"),
            rs.getString("source"),
            rs.getString("remark"),
            rs.getTimestamp("created_at").toInstant(),
            rs.getTimestamp("updated_at").toInstant()
    );

    private final JdbcTemplate jdbcTemplate;

    public CustomerRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Customer save(Customer customer) {
        Instant now = Instant.now();
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement ps = connection.prepareStatement("""
                    INSERT INTO customer (owner_id, name, phone, gender, lifecycle_stage, source, remark, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, new String[]{"id"});
            ps.setLong(1, customer.ownerId());
            ps.setString(2, customer.name());
            ps.setString(3, customer.phone());
            ps.setString(4, customer.gender() == null ? "U" : customer.gender());
            ps.setString(5, customer.lifecycleStage() == null ? "new" : customer.lifecycleStage());
            ps.setString(6, customer.source());
            ps.setString(7, customer.remark());
            ps.setTimestamp(8, Timestamp.from(now));
            ps.setTimestamp(9, Timestamp.from(now));
            return ps;
        }, keyHolder);
        Long id = keyHolder.getKey().longValue();
        return findById(id).orElseThrow();
    }

    public Optional<Customer> findById(Long id) {
        List<Customer> rows = jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM customer WHERE id = ? AND deleted_token = '0'",
                ROW_MAPPER,
                id
        );
        return rows.stream().findFirst();
    }

    public List<Customer> findByOwner(Long ownerId) {
        return jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM customer WHERE owner_id = ? AND deleted_token = '0' ORDER BY id",
                ROW_MAPPER,
                ownerId
        );
    }

    public List<Customer> findAll() {
        return jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM customer WHERE deleted_token = '0' ORDER BY id",
                ROW_MAPPER
        );
    }

    public void update(Customer customer) {
        jdbcTemplate.update("""
                UPDATE customer
                SET name = ?, phone = ?, gender = ?, lifecycle_stage = ?, source = ?, remark = ?, updated_at = ?
                WHERE id = ? AND deleted_token = '0'
                """,
                customer.name(),
                customer.phone(),
                customer.gender(),
                customer.lifecycleStage(),
                customer.source(),
                customer.remark(),
                Timestamp.from(Instant.now()),
                customer.id()
        );
    }

    public boolean softDelete(Long id) {
        return jdbcTemplate.update(
                "UPDATE customer SET deleted_token = CAST(id AS CHAR) WHERE id = ? AND deleted_token = '0'",
                id
        ) > 0;
    }
}
