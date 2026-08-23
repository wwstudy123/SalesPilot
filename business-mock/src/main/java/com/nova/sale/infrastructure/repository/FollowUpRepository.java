package com.nova.sale.infrastructure.repository;

import com.nova.sale.domain.model.FollowUp;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;

@Repository
public class FollowUpRepository {
    private static final String COLUMNS = "id, customer_id, employee_id, channel, content, next_follow_at, created_at";

    private static final RowMapper<FollowUp> ROW_MAPPER = (rs, rowNum) -> new FollowUp(
            rs.getLong("id"),
            rs.getLong("customer_id"),
            rs.getLong("employee_id"),
            rs.getString("channel"),
            rs.getString("content"),
            rs.getTimestamp("next_follow_at") == null ? null : rs.getTimestamp("next_follow_at").toInstant(),
            rs.getTimestamp("created_at").toInstant()
    );

    private final JdbcTemplate jdbcTemplate;

    public FollowUpRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public FollowUp save(FollowUp followUp) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement ps = connection.prepareStatement("""
                    INSERT INTO follow_up (customer_id, employee_id, channel, content, next_follow_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, new String[]{"id"});
            ps.setLong(1, followUp.customerId());
            ps.setLong(2, followUp.employeeId());
            ps.setString(3, followUp.channel() == null ? "chat" : followUp.channel());
            ps.setString(4, followUp.content());
            ps.setTimestamp(5, followUp.nextFollowAt() == null ? null : Timestamp.from(followUp.nextFollowAt()));
            ps.setTimestamp(6, Timestamp.from(Instant.now()));
            return ps;
        }, keyHolder);
        Long id = keyHolder.getKey().longValue();
        return jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM follow_up WHERE id = ?",
                ROW_MAPPER,
                id
        ).stream().findFirst().orElseThrow();
    }

    public List<FollowUp> findByCustomer(Long customerId) {
        return jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM follow_up WHERE customer_id = ? ORDER BY created_at DESC, id DESC",
                ROW_MAPPER,
                customerId
        );
    }
}
