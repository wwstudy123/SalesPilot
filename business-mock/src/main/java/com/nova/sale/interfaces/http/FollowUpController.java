package com.nova.sale.interfaces.http;

import com.nova.sale.application.FollowUpService;
import com.nova.sale.infrastructure.security.AuthContext;
import com.nova.sale.interfaces.dto.ApiResponse;
import com.nova.sale.interfaces.dto.FollowUpRequest;
import com.nova.sale.interfaces.dto.FollowUpResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/follow-ups")
public class FollowUpController {
    private final FollowUpService followUpService;

    public FollowUpController(FollowUpService followUpService) {
        this.followUpService = followUpService;
    }

    @PostMapping
    public ApiResponse<FollowUpResponse> create(@Valid @RequestBody FollowUpRequest request) {
        return ApiResponse.ok(FollowUpResponse.from(followUpService.create(request, AuthContext.current())));
    }
}
