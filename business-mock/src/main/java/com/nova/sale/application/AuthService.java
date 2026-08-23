package com.nova.sale.application;

import com.nova.sale.domain.model.Employee;
import com.nova.sale.infrastructure.repository.EmployeeRepository;
import com.nova.sale.infrastructure.security.JwtService;
import com.nova.sale.interfaces.dto.LoginRequest;
import com.nova.sale.interfaces.dto.LoginResponse;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class AuthService {
    private final EmployeeRepository employeeRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    public AuthService(EmployeeRepository employeeRepository, PasswordEncoder passwordEncoder, JwtService jwtService) {
        this.employeeRepository = employeeRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
    }

    public LoginResponse login(LoginRequest request) {
        Employee employee = employeeRepository.findByUsername(request.username())
                .filter(e -> passwordEncoder.matches(request.password(), e.passwordHash()))
                .orElseThrow(() -> new IllegalArgumentException("用户名或密码错误"));
        String token = jwtService.createToken(employee);
        return new LoginResponse(token, employee.id(), employee.name(), employee.role());
    }
}
