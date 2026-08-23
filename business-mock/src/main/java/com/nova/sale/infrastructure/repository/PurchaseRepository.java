package com.nova.sale.infrastructure.repository;

import com.nova.sale.domain.model.Purchase;
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
public class PurchaseRepository {
    private static final String COLUMNS =
            "id, customer_id, product_name, category, amount, quantity, purchased_at, remark, created_at";

    private static final RowMapper<Purchase> ROW_MAPPER = (rs, rowNum) -> new Purchase(
            rs.getLong("id"),
            rs.getLong("customer_id"),
            rs.getString("product_name"),
            rs.getString("category"),
            rs.getBigDecimal("amount"),
            rs.getInt("quantity"),
            rs.getTimestamp("purchased_at").toInstant(),
            rs.getString("remark"),
            rs.getTimestamp("created_at").toInstant()
    );

    private final JdbcTemplate jdbcTemplate;

    public PurchaseRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Purchase save(Purchase purchase) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement ps = connection.prepareStatement("""
                    INSERT INTO purchase (customer_id, product_name, category, amount, quantity, purchased_at, remark, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, new String[]{"id"});
            ps.setLong(1, purchase.customerId());
            ps.setString(2, purchase.productName());
            ps.setString(3, purchase.category());
            ps.setBigDecimal(4, purchase.amount());
            ps.setInt(5, purchase.quantity() == null ? 1 : purchase.quantity());
            ps.setTimestamp(6, Timestamp.from(purchase.purchasedAt() == null ? Instant.now() : purchase.purchasedAt()));
            ps.setString(7, purchase.remark());
            ps.setTimestamp(8, Timestamp.from(Instant.now()));
            return ps;
        }, keyHolder);
        Long id = keyHolder.getKey().longValue();
        return jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM purchase WHERE id = ?",
                ROW_MAPPER,
                id
        ).stream().findFirst().orElseThrow();
    }

    public List<Purchase> findByCustomer(Long customerId) {
        return jdbcTemplate.query(
                "SELECT " + COLUMNS + " FROM purchase WHERE customer_id = ? ORDER BY purchased_at DESC, id DESC",
                ROW_MAPPER,
                customerId
        );
    }
}
