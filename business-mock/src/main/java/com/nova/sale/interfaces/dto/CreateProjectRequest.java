package com.nova.sale.interfaces.dto;

import jakarta.validation.constraints.NotBlank;

public record CreateProjectRequest(
        @NotBlank String projectId,
        @NotBlank String title,
        String premise,
        String style
) {}
