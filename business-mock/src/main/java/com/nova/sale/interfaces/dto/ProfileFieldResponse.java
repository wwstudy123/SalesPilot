package com.nova.sale.interfaces.dto;

import com.nova.sale.domain.model.ProfileField;

import java.time.Instant;

public record ProfileFieldResponse(
        Long id,
        Long customerId,
        String fieldKey,
        String fieldValue,
        String evidence,
        Integer version,
        Long updatedBy,
        Instant updatedAt
) {
    public static ProfileFieldResponse from(ProfileField field) {
        return new ProfileFieldResponse(
                field.id(), field.customerId(), field.fieldKey(), field.fieldValue(),
                field.evidence(), field.version(), field.updatedBy(), field.updatedAt()
        );
    }
}
