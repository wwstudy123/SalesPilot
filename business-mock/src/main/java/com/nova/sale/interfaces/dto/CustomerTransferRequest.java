package com.nova.sale.interfaces.dto;

import jakarta.validation.constraints.NotNull;

public record CustomerTransferRequest(@NotNull Long toEmployeeId) {
}
