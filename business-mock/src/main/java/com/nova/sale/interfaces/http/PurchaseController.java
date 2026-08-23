package com.nova.sale.interfaces.http;

import com.nova.sale.application.PurchaseService;
import com.nova.sale.infrastructure.security.AuthContext;
import com.nova.sale.interfaces.dto.ApiResponse;
import com.nova.sale.interfaces.dto.PurchaseRequest;
import com.nova.sale.interfaces.dto.PurchaseResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/purchases")
public class PurchaseController {
    private final PurchaseService purchaseService;

    public PurchaseController(PurchaseService purchaseService) {
        this.purchaseService = purchaseService;
    }

    @PostMapping
    public ApiResponse<PurchaseResponse> create(@Valid @RequestBody PurchaseRequest request) {
        return ApiResponse.ok(PurchaseResponse.from(purchaseService.create(request, AuthContext.current())));
    }
}
