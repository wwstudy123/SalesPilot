package com.nova.sale.interfaces.dto;

import com.nova.sale.domain.model.Purchase;

import java.math.BigDecimal;
import java.time.Instant;

public record PurchaseResponse(
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
    public static PurchaseResponse from(Purchase purchase) {
        return new PurchaseResponse(
                purchase.id(), purchase.customerId(), purchase.productName(), purchase.category(),
                purchase.amount(), purchase.quantity(), purchase.purchasedAt(), purchase.remark(),
                purchase.createdAt()
        );
    }
}
