package com.nova.sale.domain.model;

import java.time.Instant;

public record FollowUp(
        Long id,
        Long customerId,
        Long employeeId,
        String channel,
        String content,
        Instant nextFollowAt,
        Instant createdAt
) {
}
