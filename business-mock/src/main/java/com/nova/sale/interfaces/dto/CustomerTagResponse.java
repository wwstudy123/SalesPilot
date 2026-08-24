package com.nova.sale.interfaces.dto;

import com.nova.sale.domain.model.CustomerTag;

import java.math.BigDecimal;
import java.time.Instant;

public record CustomerTagResponse(
        Long id,
        Long customerId,
        String tagKey,
        String tagName,
        String tagType,
        String evidence,
        BigDecimal confidence,
        Instant updatedAt
) {
    public static CustomerTagResponse from(CustomerTag tag) {
        return new CustomerTagResponse(
                tag.id(), tag.customerId(), tag.tagKey(), tag.tagName(), tag.tagType(),
                tag.evidence(), tag.confidence(), tag.updatedAt());
    }
}
