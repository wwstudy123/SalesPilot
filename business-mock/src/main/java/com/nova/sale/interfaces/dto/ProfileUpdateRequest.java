package com.nova.sale.interfaces.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;

import java.util.List;

/** 画像字段更新请求：审批凭证由服务层校验（无凭证 403 E_APPROVAL_REQUIRED，架构 §3.2）。 */
public record ProfileUpdateRequest(
        String approvalToken,
        @NotEmpty(message = "fields 不能为空") @Valid List<FieldUpdateItem> fields
) {
    public record FieldUpdateItem(
            @NotBlank(message = "fieldKey 不能为空") String fieldKey,
            @NotBlank(message = "fieldValue 不能为空") String fieldValue,
            @NotBlank(message = "evidence 不能为空") String evidence
    ) {
    }
}
