package com.nova.sale.infrastructure.repository;

import com.nova.sale.domain.model.CustomerTag;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;

@Repository
public class CustomerTagRepository {
    private static final RowMapper<CustomerTag> ROW_MAPPER = (rs, rowNum) -> new CustomerTag(
            rs.getLong("id"),
            rs.getLong("customer_id"),
            rs.getLong("tag_id"),
            rs.getString("tag_key"),
            rs.getString("tag_name"),
            rs.getString("tag_type"),
            rs.getString("evidence"),
            rs.getBigDecimal("confidence"),
            rs.getObject("updated_by") == null ? null : rs.getLong("updated_by"),
            rs.getTimestamp("updated_at").toInstant()
    );

    private final JdbcTemplate jdbcTemplate;

    public CustomerTagRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public List<CustomerTag> findByCustomer(Long customerId) {
        return jdbcTemplate.query("""
                SELECT ct.id, ct.customer_id, ct.tag_id, d.tag_key, d.tag_name, d.tag_type,
                       ct.evidence, ct.confidence, ct.updated_by, ct.updated_at
                FROM customer_tag ct JOIN tag_dict d ON d.id = ct.tag_id
                WHERE ct.customer_id = ? ORDER BY d.tag_type, d.tag_key
                """, ROW_MAPPER, customerId);
    }

    public Long findTagId(String tagKey) {
        List<Long> ids = jdbcTemplate.query(
                "SELECT id FROM tag_dict WHERE tag_key = ? AND active = TRUE",
                (rs, rowNum) -> rs.getLong("id"),
                tagKey
        );
        return ids.isEmpty() ? null : ids.getFirst();
    }

    /** 覆盖式保存：确认的标签集成为客户当前标签集，修正实时生效。 */
    public void replace(Long customerId, List<TagAssignment> assignments, Long updatedBy) {
        jdbcTemplate.update("DELETE FROM customer_tag WHERE customer_id = ?", customerId);
        for (TagAssignment assignment : assignments) {
            jdbcTemplate.update("""
                    INSERT INTO customer_tag (customer_id, tag_id, evidence, confidence, updated_by, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    customerId, assignment.tagId(), assignment.evidence(), assignment.confidence(), updatedBy,
                    Timestamp.from(Instant.now()));
        }
    }

    public record TagAssignment(Long tagId, String evidence, BigDecimal confidence) {
    }
}
