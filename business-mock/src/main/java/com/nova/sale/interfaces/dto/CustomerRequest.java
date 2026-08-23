package com.nova.sale.interfaces.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public record CustomerRequest(
        @NotBlank(message = "name is required") String name,
        String phone,
        @Pattern(regexp = "M|F|U", message = "gender must be M/F/U") String gender,
        @Pattern(regexp = "new|prospective|existing|churn_risk", message = "invalid lifecycle_stage") String lifecycleStage,
        String source,
        String remark,
        Long ownerId
) {
}
