package com.acme.platform.interfaces.dto;

public record ProjectResponse(
        String projectId,
        String title,
        String premise,
        String style,
        String createdAt,
        String updatedAt
) {}
