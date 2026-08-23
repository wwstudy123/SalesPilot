package com.nova.sale.application;

import com.nova.sale.domain.ForbiddenException;
import com.nova.sale.domain.NotFoundException;
import com.nova.sale.domain.model.Customer;
import com.nova.sale.infrastructure.repository.CustomerRepository;
import com.nova.sale.infrastructure.security.AuthContext;
import com.nova.sale.interfaces.dto.CustomerRequest;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 客户域应用服务。
 * 关键硬规则：客户归属校验——employee 仅自己名下客户，manager 全量。
 */
@Service
public class CustomerService {
    private final CustomerRepository customerRepository;

    public CustomerService(CustomerRepository customerRepository) {
        this.customerRepository = customerRepository;
    }

    public List<Customer> list(AuthContext current) {
        return current.isManager()
                ? customerRepository.findAll()
                : customerRepository.findByOwner(current.employeeId());
    }

    public Customer get(Long id, AuthContext current) {
        return requireOwned(id, current);
    }

    public Customer create(CustomerRequest request, AuthContext current) {
        Long ownerId = request.ownerId() != null ? request.ownerId() : current.employeeId();
        if (!current.isManager() && !ownerId.equals(current.employeeId())) {
            throw new ForbiddenException("只能在自己名下创建客户");
        }
        Customer customer = new Customer(
                null, ownerId, request.name(), request.phone(),
                request.gender(), request.lifecycleStage(), request.source(), request.remark(),
                null, null
        );
        return customerRepository.save(customer);
    }

    public Customer update(Long id, CustomerRequest request, AuthContext current) {
        Customer existing = requireOwned(id, current);
        Customer updated = new Customer(
                existing.id(), existing.ownerId(), request.name(), request.phone(),
                request.gender() == null ? existing.gender() : request.gender(),
                request.lifecycleStage() == null ? existing.lifecycleStage() : request.lifecycleStage(),
                request.source(), request.remark(),
                existing.createdAt(), existing.updatedAt()
        );
        customerRepository.update(updated);
        return customerRepository.findById(id).orElseThrow();
    }

    public Customer softDelete(Long id, AuthContext current) {
        Customer customer = requireOwned(id, current);
        customerRepository.softDelete(id);
        return customer;
    }

    /** 归属校验统一出口：不存在 404，越权 403。 */
    public Customer requireOwned(Long customerId, AuthContext current) {
        Customer customer = customerRepository.findById(customerId)
                .orElseThrow(() -> new NotFoundException("customer not found: " + customerId));
        if (!current.isManager() && !customer.ownerId().equals(current.employeeId())) {
            throw new ForbiddenException("客户不属于当前员工: " + customerId);
        }
        return customer;
    }
}
