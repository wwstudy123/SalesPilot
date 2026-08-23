package com.nova.sale.interfaces.dto;

import com.nova.sale.domain.model.Customer;

import java.time.Instant;

public record CustomerResponse(
        Long id,
        Long ownerId,
        String name,
        String phone,
        String gender,
        String lifecycleStage,
        String source,
        String remark,
        Instant createdAt,
        Instant updatedAt
) {
    public static CustomerResponse from(Customer customer) {
        return new CustomerResponse(
                customer.id(), customer.ownerId(), customer.name(), customer.phone(),
                customer.gender(), customer.lifecycleStage(), customer.source(), customer.remark(),
                customer.createdAt(), customer.updatedAt()
        );
    }
}
