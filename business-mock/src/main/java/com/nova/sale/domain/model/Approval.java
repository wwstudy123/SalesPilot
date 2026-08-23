package com.nova.sale.domain.model;

import java.time.Instant;

/** 审批凭证：write 工具必须携带，一次性消费、30min 过期。 */
public record Approval(
        Long id,
        String token,
        String tool,
        Long actorId,
        Long customerId,
        String payload,
        String idempotencyKey,
        String status,
        Instant expiresAt,
        Instant createdAt,
        Instant consumedAt
) {
    public boolean expired(Instant now) {
        return expiresAt.isBefore(now);
    }
}
