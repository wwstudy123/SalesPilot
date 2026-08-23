package com.nova.sale.infrastructure.repository;

import com.nova.sale.domain.model.ProfileField;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;

@Repository
public class ProfileFieldRepository {
    private static final String COLUMNS =
            "id, customer_id, field_key, field_value, evidence, version, updated_by, updated_at";

    private static final RowMapper<ProfileField> ROW_MAPPER = (rs, rowNum) -> new ProfileField(
            rs.getLong("id"),
            rs.getLong("customer_id"),
            rs.getString("field_key"),
            rs.getString("field_value"),
            rs.getString("evidence"),
            rs.getInt("version"),
            rs.getObject("updated_by") == null ? null : rs.getLong("updated_by"),
            rs.getTimestamp("updated_at").toInstant()
    );

    private final JdbcTemplate jdbcTemplate;

    public ProfileFieldRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public List<ProfileField> findByCustomer(Long customerId) {
        return jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM customer_profile_field WHERE customer_id = ? ORDER BY field_key",
                ROW_MAPPER,
                customerId
        );
    }

    /** 字段级 upsert：已存在则 version+1（采纳留痕：谁在何时因哪条依据改了什么）。 */
    public void upsert(Long customerId, String fieldKey, String fieldValue, String evidence, Long updatedBy) {
        jdbcTemplate.update("""
                INSERT INTO customer_profile_field (customer_id, field_key, field_value, evidence, version, updated_by, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON DUPLICATE KEY UPDATE
                    field_value = VALUES(field_value),
                    evidence = VALUES(evidence),
                    version = version + 1,
                    updated_by = VALUES(updated_by),
                    updated_at = VALUES(updated_at)
                """,
                customerId,
                fieldKey,
                fieldValue,
                evidence,
                updatedBy,
                Timestamp.from(Instant.now())
        );
    }
}
