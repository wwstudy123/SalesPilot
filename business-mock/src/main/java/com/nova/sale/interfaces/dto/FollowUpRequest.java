package com.nova.sale.interfaces.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;

import java.time.Instant;

public record FollowUpRequest(
        @NotNull(message = "customerId is required") Long customerId,
        @Pattern(regexp = "chat|phone|visit|wechat", message = "invalid channel") String channel,
        @NotBlank(message = "content is required") String content,
        Instant nextFollowAt
) {
}
