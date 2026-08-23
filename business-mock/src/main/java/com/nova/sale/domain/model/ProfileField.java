package com.nova.sale.domain.model;

import java.time.Instant;

/** 客户画像字段（字段级版本与依据，采纳留痕）。 */
public record ProfileField(
        Long id,
        Long customerId,
        String fieldKey,
        String fieldValue,
        String evidence,
        Integer version,
        Long updatedBy,
        Instant updatedAt
) {
}
