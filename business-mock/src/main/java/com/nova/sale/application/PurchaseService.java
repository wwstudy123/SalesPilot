package com.nova.sale.application;

import com.nova.sale.domain.model.Purchase;
import com.nova.sale.infrastructure.repository.PurchaseRepository;
import com.nova.sale.infrastructure.security.AuthContext;
import com.nova.sale.interfaces.dto.PurchaseRequest;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class PurchaseService {
    private final PurchaseRepository purchaseRepository;
    private final CustomerService customerService;

    public PurchaseService(PurchaseRepository purchaseRepository, CustomerService customerService) {
        this.purchaseRepository = purchaseRepository;
        this.customerService = customerService;
    }

    public List<Purchase> listByCustomer(Long customerId, AuthContext current) {
        customerService.requireOwned(customerId, current);
        return purchaseRepository.findByCustomer(customerId);
    }

    public Purchase create(PurchaseRequest request, AuthContext current) {
        customerService.requireOwned(request.customerId(), current);
        Purchase purchase = new Purchase(
                null, request.customerId(), request.productName(), request.category(),
                request.amount(), request.quantity(), request.purchasedAt(), request.remark(), null
        );
        return purchaseRepository.save(purchase);
    }
}
