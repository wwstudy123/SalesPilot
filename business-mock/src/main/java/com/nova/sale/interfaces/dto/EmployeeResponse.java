package com.nova.sale.interfaces.dto;

import com.nova.sale.domain.model.Employee;

public record EmployeeResponse(
        Long id,
        String username,
        String name,
        String role,
        String phone
) {
    public static EmployeeResponse from(Employee employee) {
        return new EmployeeResponse(
                employee.id(), employee.username(), employee.name(), employee.role(), employee.phone()
        );
    }
}
