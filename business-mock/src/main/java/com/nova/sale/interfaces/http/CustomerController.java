package com.nova.sale.interfaces.http;

import com.nova.sale.application.CustomerService;
import com.nova.sale.application.FollowUpService;
import com.nova.sale.application.ProfileService;
import com.nova.sale.application.PurchaseService;
import com.nova.sale.infrastructure.security.AuthContext;
import com.nova.sale.interfaces.dto.ApiResponse;
import com.nova.sale.interfaces.dto.CustomerRequest;
import com.nova.sale.interfaces.dto.CustomerResponse;
import com.nova.sale.interfaces.dto.FollowUpResponse;
import com.nova.sale.interfaces.dto.ProfileFieldResponse;
import com.nova.sale.interfaces.dto.ProfileUpdateRequest;
import com.nova.sale.interfaces.dto.PurchaseResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/customers")
public class CustomerController {
    private final CustomerService customerService;
    private final FollowUpService followUpService;
    private final PurchaseService purchaseService;
    private final ProfileService profileService;

    public CustomerController(CustomerService customerService, FollowUpService followUpService,
                              PurchaseService purchaseService, ProfileService profileService) {
        this.customerService = customerService;
        this.followUpService = followUpService;
        this.purchaseService = purchaseService;
        this.profileService = profileService;
    }

    @GetMapping
    public ApiResponse<List<CustomerResponse>> list() {
        return ApiResponse.ok(customerService.list(AuthContext.current()).stream()
                .map(CustomerResponse::from).toList());
    }

    @GetMapping("/{customerId}")
    public ApiResponse<CustomerResponse> get(@PathVariable Long customerId) {
        return ApiResponse.ok(CustomerResponse.from(customerService.get(customerId, AuthContext.current())));
    }

    @PostMapping
    public ApiResponse<CustomerResponse> create(@Valid @RequestBody CustomerRequest request) {
        return ApiResponse.ok(CustomerResponse.from(customerService.create(request, AuthContext.current())));
    }

    @PutMapping("/{customerId}")
    public ApiResponse<CustomerResponse> update(@PathVariable Long customerId,
                                                @Valid @RequestBody CustomerRequest request) {
        return ApiResponse.ok(CustomerResponse.from(customerService.update(customerId, request, AuthContext.current())));
    }

    @DeleteMapping("/{customerId}")
    public ApiResponse<CustomerResponse> delete(@PathVariable Long customerId) {
        return ApiResponse.ok(CustomerResponse.from(customerService.softDelete(customerId, AuthContext.current())));
    }

    @GetMapping("/{customerId}/follow-ups")
    public ApiResponse<List<FollowUpResponse>> followUps(@PathVariable Long customerId) {
        return ApiResponse.ok(followUpService.listByCustomer(customerId, AuthContext.current()).stream()
                .map(FollowUpResponse::from).toList());
    }

    @GetMapping("/{customerId}/purchases")
    public ApiResponse<List<PurchaseResponse>> purchases(@PathVariable Long customerId) {
        return ApiResponse.ok(purchaseService.listByCustomer(customerId, AuthContext.current()).stream()
                .map(PurchaseResponse::from).toList());
    }

    @GetMapping("/{customerId}/profile")
    public ApiResponse<List<ProfileFieldResponse>> profile(@PathVariable Long customerId) {
        return ApiResponse.ok(profileService.getProfile(customerId, AuthContext.current()).stream()
                .map(ProfileFieldResponse::from).toList());
    }

    /** 画像字段更新：HITL 闸门，必须携带并消费 approval_token（无凭证 403）。 */
    @PutMapping("/{customerId}/profile/fields")
    public ApiResponse<List<ProfileFieldResponse>> updateProfileFields(
            @PathVariable Long customerId, @Valid @RequestBody ProfileUpdateRequest request) {
        List<ProfileService.FieldUpdate> updates = request.fields().stream()
                .map(item -> new ProfileService.FieldUpdate(item.fieldKey(), item.fieldValue(), item.evidence()))
                .toList();
        return ApiResponse.ok(profileService.applyUpdates(customerId, updates,
                request.approvalToken(), AuthContext.current()).stream()
                .map(ProfileFieldResponse::from).toList());
    }
}
