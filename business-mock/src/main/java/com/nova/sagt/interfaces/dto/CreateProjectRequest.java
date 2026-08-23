package com.nova.sagt.interfaces.dto;

import jakarta.validation.constraints.NotBlank;

public record CreateProjectRequest(
        @NotBlank String projectId,
        @NotBlank String title,
        String premise,
        String style
) {}
