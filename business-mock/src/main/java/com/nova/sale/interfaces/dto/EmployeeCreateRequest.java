package com.nova.sale.interfaces.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record EmployeeCreateRequest(
        @NotBlank(message = "用户名不能为空")
        @Size(min = 3, max = 32, message = "用户名长度 3~32")
        String username,

        @NotBlank(message = "姓名不能为空")
        @Size(max = 32, message = "姓名过长")
        String name,

        @NotBlank(message = "密码不能为空")
        @Size(min = 6, max = 64, message = "密码长度 6~64")
        String password,

        @Pattern(regexp = "employee|manager", message = "角色仅支持 employee/manager")
        String role,

        String phone
) {
}
