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
    private final AiEventNotifier aiEventNotifier;

    public FollowUpService(FollowUpRepository followUpRepository, CustomerService customerService,
                           AiEventNotifier aiEventNotifier) {
        this.followUpRepository = followUpRepository;
        this.customerService = customerService;
        this.aiEventNotifier = aiEventNotifier;
    }

    public List<FollowUp> listByCustomer(Long customerId, AuthContext current) {
        customerService.requireOwned(customerId, current);
        return followUpRepository.findByCustomer(customerId);
    }

    public FollowUp create(FollowUpRequest request, AuthContext current, String jwt) {
        customerService.requireOwned(request.customerId(), current);
        FollowUp followUp = new FollowUp(
                null, request.customerId(), current.employeeId(),
                request.channel(), request.content(), request.nextFollowAt(), null
        );
        FollowUp saved = followUpRepository.save(followUp);
        // M4 触发链路：新跟进落库 → 通知 sale-agent 增量画像（验收：30s 内出提案）
        aiEventNotifier.followUpCreated(saved.id(), saved.customerId(), saved.employeeId(), jwt);
        return saved;
    }
}
