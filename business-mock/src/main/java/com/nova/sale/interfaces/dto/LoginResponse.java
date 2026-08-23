package com.nova.sale.interfaces.dto;

public record LoginResponse(
        String token,
        Long employeeId,
        String name,
        String role
) {
}
