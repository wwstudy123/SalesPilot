package com.acme.platform.interfaces.dto;

public record ErrorResponse(
        String code,
        String message
) {}
