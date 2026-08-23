package com.nova.sale.application;

import com.nova.sale.domain.model.FollowUp;
import com.nova.sale.infrastructure.repository.FollowUpRepository;
import com.nova.sale.infrastructure.security.AuthContext;
import com.nova.sale.interfaces.dto.FollowUpRequest;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class FollowUpService {
    private final FollowUpRepository followUpRepository;
    private final CustomerService customerService;

    public FollowUpService(FollowUpRepository followUpRepository, CustomerService customerService) {
        this.followUpRepository = followUpRepository;
        this.customerService = customerService;
    }

    public List<FollowUp> listByCustomer(Long customerId, AuthContext current) {
        customerService.requireOwned(customerId, current);
        return followUpRepository.findByCustomer(customerId);
    }

    public FollowUp create(FollowUpRequest request, AuthContext current) {
        customerService.requireOwned(request.customerId(), current);
        FollowUp followUp = new FollowUp(
                null, request.customerId(), current.employeeId(),
                request.channel(), request.content(), request.nextFollowAt(), null
        );
        return followUpRepository.save(followUp);
    }
}
