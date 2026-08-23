package com.nova.sale.interfaces.http;

import com.nova.sale.application.ApprovalService;
import com.nova.sale.infrastructure.security.AuthContext;
import com.nova.sale.interfaces.dto.ApiResponse;
import com.nova.sale.interfaces.dto.ApprovalRequest;
import com.nova.sale.interfaces.dto.ApprovalRequest.ApprovalResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 审批凭证签发：sale-agent 在员工确认提案后换取 approval_token（架构 §7.3）。 */
@RestController
@RequestMapping("/api/v1/approvals")
public class ApprovalController {
    private final ApprovalService approvalService;
    private final ObjectMapper objectMapper;

    public ApprovalController(ApprovalService approvalService, ObjectMapper objectMapper) {
        this.approvalService = approvalService;
        this.objectMapper = objectMapper;
    }

    @PostMapping
    public ApiResponse<ApprovalResponse> issue(@Valid @RequestBody ApprovalRequest request)
            throws JsonProcessingException {
        String payload = request.payload() == null ? "{}" : objectMapper.writeValueAsString(request.payload());
        return ApiResponse.ok(ApprovalResponse.from(approvalService.issue(
                request.tool(), request.customerId(), payload, request.idempotencyKey(), AuthContext.current())));
    }
}
