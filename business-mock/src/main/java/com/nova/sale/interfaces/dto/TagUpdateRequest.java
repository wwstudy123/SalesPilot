package com.nova.sale.interfaces.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;
import java.util.List;

public record TagUpdateRequest(
        String approvalToken,
        @NotEmpty(message = "tags 不能为空") @Valid List<TagItem> tags
) {
    public record TagItem(
            @NotBlank(message = "tagKey 不能为空") String tagKey,
            @NotBlank(message = "evidence 不能为空") String evidence,
            @NotNull @DecimalMin(value = "0.0") @DecimalMax(value = "1.0") BigDecimal confidence
    ) {
    }
}
