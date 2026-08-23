package com.nova.sale.interfaces.http;

import com.nova.sale.interfaces.dto.ApiResponse;
import com.nova.sale.interfaces.dto.HealthResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
public class HealthController {
    @GetMapping("/health")
    public ApiResponse<HealthResponse> health() {
        return ApiResponse.ok(new HealthResponse("ok", "business-mock"));
    }
}
