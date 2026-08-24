package com.nova.sale.interfaces.dto;

import jakarta.validation.constraints.Pattern;

public record EmployeeRoleRequest(@Pattern(regexp = "employee|manager") String role) {
}
