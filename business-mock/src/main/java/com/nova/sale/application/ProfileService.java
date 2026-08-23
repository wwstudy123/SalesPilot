package com.nova.sale.application;

import com.nova.sale.domain.model.ProfileField;
import com.nova.sale.infrastructure.repository.ProfileFieldRepository;
import com.nova.sale.infrastructure.security.AuthContext;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;

/**
 * 画像域应用服务：字段级读写。
 * 硬规则：写操作（字段更新）必须携带并消费 approval_token（HITL 闸门，架构 §7.3）。
 */
@Service
public class ProfileService {
    /** 画像字段白名单（需求 §13：偏好/需求/价值分层/阶段/敏感点/最近关注点）。 */
    public static final Set<String> FIELD_KEYS = Set.of(
            "preference", "demand", "value_tier", "lifecycle_stage", "sensitive_point", "recent_focus"
    );

    private final ProfileFieldRepository profileFieldRepository;
    private final CustomerService customerService;
    private final ApprovalService approvalService;

    public ProfileService(ProfileFieldRepository profileFieldRepository,
                          CustomerService customerService,
                          ApprovalService approvalService) {
        this.profileFieldRepository = profileFieldRepository;
        this.customerService = customerService;
        this.approvalService = approvalService;
    }

    public List<ProfileField> getProfile(Long customerId, AuthContext current) {
        customerService.requireOwned(customerId, current);
        return profileFieldRepository.findByCustomer(customerId);
    }

    /** 字段级更新：先消费审批凭证（无凭证 100% 拒），再逐字段 upsert（version+1 留痕）。 */
    public List<ProfileField> applyUpdates(Long customerId, List<FieldUpdate> updates,
                                           String approvalToken, AuthContext current) {
        customerService.requireOwned(customerId, current);
        if (updates == null || updates.isEmpty()) {
            throw new IllegalArgumentException("字段更新列表不能为空");
        }
        for (FieldUpdate update : updates) {
            if (!FIELD_KEYS.contains(update.fieldKey())) {
                throw new IllegalArgumentException("未知画像字段: " + update.fieldKey());
            }
        }
        approvalService.consume(approvalToken, "update_profile_field", customerId);
        for (FieldUpdate update : updates) {
            profileFieldRepository.upsert(customerId, update.fieldKey(), update.fieldValue(),
                    update.evidence(), current.employeeId());
        }
        return profileFieldRepository.findByCustomer(customerId);
    }

    public record FieldUpdate(String fieldKey, String fieldValue, String evidence) {
    }
}
