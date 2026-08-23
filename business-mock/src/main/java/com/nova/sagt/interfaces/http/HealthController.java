package com.nova.sagt.interfaces.http;

import com.nova.sagt.interfaces.dto.ApiResponse;
import com.nova.sagt.interfaces.dto.HealthResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
public class HealthController {
    @GetMapping("/health")
    public ApiResponse<HealthResponse> health() {
        return ApiResponse.ok(new HealthResponse("ok", "java-platform"));
    }
}
