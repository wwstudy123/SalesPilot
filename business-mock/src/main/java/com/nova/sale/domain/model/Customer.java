package com.nova.sale.domain.model;

import java.time.Instant;

public record Customer(
        Long id,
        Long ownerId,
        String name,
        String phone,
        String gender,
        String lifecycleStage,
        String source,
        String remark,
        Instant createdAt,
        Instant updatedAt
) {
}
