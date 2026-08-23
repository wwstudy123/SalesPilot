package com.nova.sale.infrastructure.security;

/** 当前登录员工上下文（从 SecurityContext 提取）。 */
public record AuthContext(Long employeeId, String username, String role) {

    public boolean isManager() {
        return "manager".equals(role);
    }

    public static AuthContext current() {
        Object principal = org.springframework.security.core.context.SecurityContextHolder
                .getContext().getAuthentication().getPrincipal();
        if (principal instanceof AuthContext authContext) {
            return authContext;
        }
        throw new IllegalStateException("no authenticated employee in context");
    }
}
