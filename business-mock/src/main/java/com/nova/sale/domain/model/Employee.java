package com.nova.sale.domain.model;

import java.time.Instant;

public record Employee(
        Long id,
        String username,
        String passwordHash,
        String name,
        String role,
        String phone,
        Instant createdAt,
        Instant updatedAt
) {
    public boolean isManager() {
        return "manager".equals(role);
    }
}
