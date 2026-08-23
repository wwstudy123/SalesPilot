package com.nova.sale.interfaces.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.math.BigDecimal;
import java.time.Instant;

public record PurchaseRequest(
        @NotNull(message = "customerId is required") Long customerId,
        @NotBlank(message = "productName is required") String productName,
        @NotBlank(message = "category is required") String category,
        @NotNull(message = "amount is required") @Positive(message = "amount must be positive") BigDecimal amount,
        @Positive(message = "quantity must be positive") Integer quantity,
        Instant purchasedAt,
        String remark
) {
}
