package com.nova.sale.application;

import com.nova.sale.infrastructure.repository.InMemoryProjectRepository;
import com.nova.sale.interfaces.dto.CreateProjectRequest;
import com.nova.sale.interfaces.dto.ProjectResponse;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ProjectApplicationServiceTest {
    @Test
    void createGetListDeleteRoundTrip() {
        ProjectApplicationService service = new ProjectApplicationService(new InMemoryProjectRepository());

        ProjectResponse created = service.createProject(new CreateProjectRequest("demo", "Demo Project", "a premise", null));
        assertThat(created.projectId()).isEqualTo("demo");
        assertThat(created.style()).isEqualTo("default");

        assertThat(service.getProject("demo").title()).isEqualTo("Demo Project");
        assertThat(service.listProjects().items()).hasSize(1);

        service.deleteProject("demo");
        assertThat(service.listProjects().items()).isEmpty();
    }
}
