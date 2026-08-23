package com.nova.sale.domain.model;

import java.math.BigDecimal;
import java.time.Instant;

public record Purchase(
        Long id,
        Long customerId,
        String productName,
        String category,
        BigDecimal amount,
        Integer quantity,
        Instant purchasedAt,
        String remark,
        Instant createdAt
) {
}
