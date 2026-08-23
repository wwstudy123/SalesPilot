package com.nova.sale.application;

import com.nova.sale.domain.ForbiddenException;
import com.nova.sale.domain.model.Approval;
import com.nova.sale.infrastructure.repository.ApprovalRepository;
import com.nova.sale.infrastructure.security.AuthContext;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;

/**
 * 审批凭证服务（架构 §3.2）：write 操作必须携带 approval_token。
 * 凭证一次性消费、30min 过期；无凭证/无效凭证/越凭证范围一律 403。
 */
@Service
public class ApprovalService {
    private static final Duration TTL = Duration.ofMinutes(30);
    private static final SecureRandom RANDOM = new SecureRandom();

    private final ApprovalRepository approvalRepository;
    private final CustomerService customerService;

    public ApprovalService(ApprovalRepository approvalRepository, CustomerService customerService) {
        this.approvalRepository = approvalRepository;
        this.customerService = customerService;
    }

    /** 签发凭证：员工确认后由 sale-agent 换取，绑定工具与客户（不可跨用）。 */
    public Approval issue(String tool, Long customerId, String payload, String idempotencyKey, AuthContext current) {
        customerService.requireOwned(customerId, current);
        byte[] raw = new byte[16];
        RANDOM.nextBytes(raw);
        Approval approval = new Approval(
                null, HexFormat.of().formatHex(raw), tool, current.employeeId(), customerId,
                payload, idempotencyKey, "pending", Instant.now().plus(TTL), null, null
        );
        return approvalRepository.save(approval);
    }

    /** 消费凭证：校验有效性后 CAS 置 consumed；任何失败路径都抛 403（E_APPROVAL_*）。 */
    public void consume(String token, String expectedTool, Long customerId) {
        if (token == null || token.isBlank()) {
            throw new ForbiddenException("E_APPROVAL_REQUIRED: write 操作必须携带审批凭证");
        }
        Approval approval = approvalRepository.findByToken(token)
                .orElseThrow(() -> new ForbiddenException("E_APPROVAL_INVALID: 凭证不存在"));
        if (!approval.tool().equals(expectedTool)) {
            throw new ForbiddenException("E_APPROVAL_MISMATCH: 凭证与工具不匹配");
        }
        if (!approval.customerId().equals(customerId)) {
            throw new ForbiddenException("E_APPROVAL_MISMATCH: 凭证与客户不匹配");
        }
        if (approval.expired(Instant.now())) {
            throw new ForbiddenException("E_APPROVAL_EXPIRED: 凭证已过期（30min）");
        }
        if (!"pending".equals(approval.status())) {
            throw new ForbiddenException("E_APPROVAL_USED: 凭证已被消费");
        }
        if (!approvalRepository.consume(token, Instant.now())) {
            throw new ForbiddenException("E_APPROVAL_USED: 凭证已被并发消费");
        }
    }
}
