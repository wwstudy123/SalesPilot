package com.nova.sale.interfaces.dto;

public record ErrorResponse(
        String code,
        String message
) {}
