package com.nova.sale.domain.model;

import java.math.BigDecimal;
import java.time.Instant;

/** 生效客户标签，保留 AI/员工提供的依据与置信度。 */
public record CustomerTag(
        Long id,
        Long customerId,
        Long tagId,
        String tagKey,
        String tagName,
        String tagType,
        String evidence,
        BigDecimal confidence,
        Long updatedBy,
        Instant updatedAt
) {
}
