package com.nova.sale.interfaces.dto;

import com.nova.sale.domain.model.Approval;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.Map;

/** 签发审批凭证请求（sale-agent 在员工确认提案后换取 token）。 */
public record ApprovalRequest(
        @NotBlank(message = "tool 不能为空") String tool,
        @NotNull(message = "customerId 不能为空") Long customerId,
        Map<String, Object> payload,
        @NotBlank(message = "idempotencyKey 不能为空") String idempotencyKey
) {
    public record ApprovalResponse(
            String token,
            String tool,
            Long customerId,
            String idempotencyKey,
            String status,
            Instant expiresAt
    ) {
        public static ApprovalResponse from(Approval approval) {
            return new ApprovalResponse(
                    approval.token(), approval.tool(), approval.customerId(),
                    approval.idempotencyKey(), approval.status(), approval.expiresAt()
            );
        }
    }
}
