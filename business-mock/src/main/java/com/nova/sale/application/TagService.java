package com.nova.sale.application;

import com.nova.sale.domain.model.CustomerTag;
import com.nova.sale.infrastructure.repository.CustomerTagRepository;
import com.nova.sale.infrastructure.security.AuthContext;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Service
public class TagService {
    private final CustomerTagRepository repository;
    private final CustomerService customerService;
    private final ApprovalService approvalService;

    public TagService(CustomerTagRepository repository, CustomerService customerService, ApprovalService approvalService) {
        this.repository = repository;
        this.customerService = customerService;
        this.approvalService = approvalService;
    }

    public List<CustomerTag> getTags(Long customerId, AuthContext current) {
        customerService.requireOwned(customerId, current);
        return repository.findByCustomer(customerId);
    }

    public List<CustomerTag> saveTags(Long customerId, List<TagUpdate> tags, String approvalToken, AuthContext current) {
        customerService.requireOwned(customerId, current);
        if (tags == null || tags.isEmpty()) {
            throw new IllegalArgumentException("标签列表不能为空");
        }
        List<CustomerTagRepository.TagAssignment> assignments = new ArrayList<>();
        for (TagUpdate tag : tags) {
            Long tagId = repository.findTagId(tag.tagKey());
            if (tagId == null) {
                throw new IllegalArgumentException("未知或停用标签: " + tag.tagKey());
            }
            if (tag.confidence().compareTo(BigDecimal.ZERO) < 0 || tag.confidence().compareTo(BigDecimal.ONE) > 0) {
                throw new IllegalArgumentException("置信度必须在 0~1");
            }
            assignments.add(new CustomerTagRepository.TagAssignment(tagId, tag.evidence(), tag.confidence()));
        }
        approvalService.consume(approvalToken, "save_tags", customerId);
        repository.replace(customerId, assignments, current.employeeId());
        return repository.findByCustomer(customerId);
    }

    public record TagUpdate(String tagKey, String evidence, BigDecimal confidence) {
    }
}
