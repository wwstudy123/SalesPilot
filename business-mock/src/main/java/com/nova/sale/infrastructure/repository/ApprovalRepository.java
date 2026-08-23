package com.nova.sale.infrastructure.repository;

import com.nova.sale.domain.model.Approval;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

@Repository
public class ApprovalRepository {
    private static final String COLUMNS =
            "id, token, tool, actor_id, customer_id, payload, idempotency_key, status, expires_at, created_at, consumed_at";

    private static final RowMapper<Approval> ROW_MAPPER = (rs, rowNum) -> new Approval(
            rs.getLong("id"),
            rs.getString("token"),
            rs.getString("tool"),
            rs.getLong("actor_id"),
            rs.getLong("customer_id"),
            rs.getString("payload"),
            rs.getString("idempotency_key"),
            rs.getString("status"),
            rs.getTimestamp("expires_at").toInstant(),
            rs.getTimestamp("created_at").toInstant(),
            rs.getTimestamp("consumed_at") == null ? null : rs.getTimestamp("consumed_at").toInstant()
    );

    private final JdbcTemplate jdbcTemplate;

    public ApprovalRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Approval save(Approval approval) {
        jdbcTemplate.update("""
                INSERT INTO approval (token, tool, actor_id, customer_id, payload, idempotency_key, status, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                approval.token(),
                approval.tool(),
                approval.actorId(),
                approval.customerId(),
                approval.payload(),
                approval.idempotencyKey(),
                approval.status(),
                Timestamp.from(approval.expiresAt()),
                Timestamp.from(Instant.now())
        );
        return findByToken(approval.token()).orElseThrow();
    }

    public Optional<Approval> findByToken(String token) {
        List<Approval> rows = jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM approval WHERE token = ?",
                ROW_MAPPER,
                token
        );
        return rows.stream().findFirst();
    }

    /** CAS 消费凭证：仅 pending 且未过期可被一次性消费（并发/重放拦截）。 */
    public boolean consume(String token, Instant now) {
        return jdbcTemplate.update("""
                UPDATE approval SET status = 'consumed', consumed_at = ?
                WHERE token = ? AND status = 'pending' AND expires_at > ?
                """,
                Timestamp.from(now),
                token,
                Timestamp.from(now)
        ) > 0;
    }
}
