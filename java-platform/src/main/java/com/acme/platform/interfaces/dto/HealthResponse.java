package com.acme.platform.interfaces.dto;

public record HealthResponse(
        String status,
        String service
) {}
