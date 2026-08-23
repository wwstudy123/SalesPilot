package com.nova.sagt.interfaces.http;

import com.nova.sagt.application.ProjectApplicationService;
import com.nova.sagt.interfaces.dto.ApiResponse;
import com.nova.sagt.interfaces.dto.CreateProjectRequest;
import com.nova.sagt.interfaces.dto.ProjectListResponse;
import com.nova.sagt.interfaces.dto.ProjectResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/projects")
public class ProjectController {
    private final ProjectApplicationService projectService;

    public ProjectController(ProjectApplicationService projectService) {
        this.projectService = projectService;
    }

    @GetMapping
    public ApiResponse<ProjectListResponse> list() {
        return ApiResponse.ok(projectService.listProjects());
    }

    @GetMapping("/{projectId}")
    public ApiResponse<ProjectResponse> get(@PathVariable String projectId) {
        return ApiResponse.ok(projectService.getProject(projectId));
    }

    @PostMapping
    public ApiResponse<ProjectResponse> create(@Valid @RequestBody CreateProjectRequest request) {
        return ApiResponse.ok(projectService.createProject(request));
    }

    @DeleteMapping("/{projectId}")
    public ApiResponse<ProjectResponse> delete(@PathVariable String projectId) {
        return ApiResponse.ok(projectService.deleteProject(projectId));
    }
}
