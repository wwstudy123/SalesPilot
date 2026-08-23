package com.nova.sale.interfaces.dto;

import com.nova.sale.domain.model.FollowUp;

import java.time.Instant;

public record FollowUpResponse(
        Long id,
        Long customerId,
        Long employeeId,
        String channel,
        String content,
        Instant nextFollowAt,
        Instant createdAt
) {
    public static FollowUpResponse from(FollowUp followUp) {
        return new FollowUpResponse(
                followUp.id(), followUp.customerId(), followUp.employeeId(),
                followUp.channel(), followUp.content(), followUp.nextFollowAt(), followUp.createdAt()
        );
    }
}
