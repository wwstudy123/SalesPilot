package com.nova.sale.interfaces.http;

import com.nova.sale.domain.NotFoundException;
import com.nova.sale.infrastructure.repository.EmployeeRepository;
import com.nova.sale.infrastructure.security.AuthContext;
import com.nova.sale.interfaces.dto.ApiResponse;
import com.nova.sale.interfaces.dto.EmployeeResponse;
import com.nova.sale.interfaces.dto.EmployeeRoleRequest;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/employees")
public class EmployeeController {
    private final EmployeeRepository employeeRepository;

    public EmployeeController(EmployeeRepository employeeRepository) {
        this.employeeRepository = employeeRepository;
    }

    /** 列表仅 manager 可见（SecurityConfig 中 hasRole MANAGER）。 */
    @GetMapping
    public ApiResponse<List<EmployeeResponse>> list() {
        return ApiResponse.ok(employeeRepository.findAll().stream().map(EmployeeResponse::from).toList());
    }

    @GetMapping("/me")
    public ApiResponse<EmployeeResponse> me() {
        AuthContext current = AuthContext.current();
        return ApiResponse.ok(EmployeeResponse.from(
                employeeRepository.findById(current.employeeId())
                        .orElseThrow(() -> new NotFoundException("employee not found: " + current.employeeId()))
        ));
    }

    @PutMapping("/{employeeId}/role")
    public ApiResponse<EmployeeResponse> updateRole(
            @PathVariable Long employeeId, @Valid @RequestBody EmployeeRoleRequest request) {
        if (!AuthContext.current().isManager()) {
            throw new com.nova.sale.domain.ForbiddenException("仅管理员可修改角色");
        }
        employeeRepository.findById(employeeId)
                .orElseThrow(() -> new NotFoundException("employee not found: " + employeeId));
        employeeRepository.updateRole(employeeId, request.role());
        return ApiResponse.ok(EmployeeResponse.from(employeeRepository.findById(employeeId).orElseThrow()));
    }
}
