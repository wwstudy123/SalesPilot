package com.nova.sale.interfaces.http;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.HashMap;
import java.util.Map;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * M1 验收：认证（JWT）+ employee/customer/follow_up/purchase CRUD + 客户归属校验（越权 403）。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class CustomerApiIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbc;

    @Autowired
    private ObjectMapper objectMapper;

    private String zhangToken;
    private String liToken;
    private String managerToken;

    @BeforeEach
    void setUp() throws Exception {
        jdbc.update("DELETE FROM purchase");
        jdbc.update("DELETE FROM follow_up");
        jdbc.update("DELETE FROM customer");
        jdbc.update("DELETE FROM employee");
        jdbc.update("INSERT INTO employee (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                "zhangsan", "{noop}pass123", "小张", "employee");
        jdbc.update("INSERT INTO employee (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                "lisi", "{noop}pass123", "小李", "employee");
        jdbc.update("INSERT INTO employee (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                "admin", "{noop}admin123", "王店长", "manager");
        zhangToken = login("zhangsan", "pass123");
        liToken = login("lisi", "pass123");
        managerToken = login("admin", "admin123");
    }

    private String login(String username, String password) throws Exception {
        String body = mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("username", username, "password", password))))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(java.nio.charset.StandardCharsets.UTF_8);
        return objectMapper.readTree(body).path("data").path("token").asText();
    }

    private long createCustomer(String token, String name) throws Exception {
        Map<String, Object> request = new HashMap<>();
        request.put("name", name);
        request.put("lifecycleStage", "prospective");
        String body = mockMvc.perform(post("/api/v1/customers")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(java.nio.charset.StandardCharsets.UTF_8);
        return objectMapper.readTree(body).path("data").path("id").asLong();
    }

    @Test
    void loginWithWrongPasswordReturns400() throws Exception {
        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("username", "zhangsan", "password", "wrong"))))
                .andExpect(status().isBadRequest());
    }

    @Test
    void unauthenticatedRequestReturns401() throws Exception {
        mockMvc.perform(get("/api/v1/customers")).andExpect(status().isUnauthorized());
    }

    @Test
    void employeeSeesOnlyOwnCustomers() throws Exception {
        createCustomer(zhangToken, "客户A");
        createCustomer(liToken, "客户B");

        JsonNode zhangList = objectMapper.readTree(mockMvc.perform(get("/api/v1/customers")
                        .header("Authorization", "Bearer " + zhangToken))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(java.nio.charset.StandardCharsets.UTF_8));
        org.assertj.core.api.Assertions.assertThat(zhangList.path("data")).hasSize(1);
        org.assertj.core.api.Assertions.assertThat(zhangList.path("data").get(0).path("name").asText()).isEqualTo("客户A");

        JsonNode managerList = objectMapper.readTree(mockMvc.perform(get("/api/v1/customers")
                        .header("Authorization", "Bearer " + managerToken))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(java.nio.charset.StandardCharsets.UTF_8));
        org.assertj.core.api.Assertions.assertThat(managerList.path("data")).hasSize(2);
    }

    @Test
    void crossOwnerAccessReturns403() throws Exception {
        long customerId = createCustomer(zhangToken, "客户A");

        mockMvc.perform(get("/api/v1/customers/" + customerId)
                        .header("Authorization", "Bearer " + liToken))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("FORBIDDEN"));

        mockMvc.perform(get("/api/v1/customers/" + customerId)
                        .header("Authorization", "Bearer " + managerToken))
                .andExpect(status().isOk());
    }

    @Test
    void employeeListOnlyForManager() throws Exception {
        mockMvc.perform(get("/api/v1/employees").header("Authorization", "Bearer " + zhangToken))
                .andExpect(status().isForbidden());
        mockMvc.perform(get("/api/v1/employees").header("Authorization", "Bearer " + managerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(3));
        mockMvc.perform(get("/api/v1/employees/me").header("Authorization", "Bearer " + zhangToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.name").value("小张"));
    }

    @Test
    void followUpAndPurchaseWithOwnershipCheck() throws Exception {
        long customerId = createCustomer(zhangToken, "客户A");

        mockMvc.perform(post("/api/v1/follow-ups")
                        .header("Authorization", "Bearer " + zhangToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"customerId\":" + customerId + ",\"channel\":\"chat\",\"content\":\"客户表示再考虑考虑\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.content").value("客户表示再考虑考虑"));

        mockMvc.perform(post("/api/v1/follow-ups")
                        .header("Authorization", "Bearer " + liToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"customerId\":" + customerId + ",\"channel\":\"phone\",\"content\":\"越权跟进\"}"))
                .andExpect(status().isForbidden());

        mockMvc.perform(post("/api/v1/purchases")
                        .header("Authorization", "Bearer " + zhangToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"customerId\":" + customerId + ",\"productName\":\"保湿面霜\",\"category\":\"美妆\",\"amount\":299.00,\"quantity\":1}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.productName").value("保湿面霜"));

        mockMvc.perform(get("/api/v1/customers/" + customerId + "/follow-ups")
                        .header("Authorization", "Bearer " + zhangToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(1));
        mockMvc.perform(get("/api/v1/customers/" + customerId + "/purchases")
                        .header("Authorization", "Bearer " + zhangToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(1));
    }

    @Test
    void softDeleteThenReturns404() throws Exception {
        long customerId = createCustomer(zhangToken, "客户A");

        mockMvc.perform(delete("/api/v1/customers/" + customerId)
                        .header("Authorization", "Bearer " + zhangToken))
                .andExpect(status().isOk());

        mockMvc.perform(get("/api/v1/customers/" + customerId)
                        .header("Authorization", "Bearer " + managerToken))
                .andExpect(status().isNotFound());

        org.assertj.core.api.Assertions.assertThat(
                jdbc.queryForObject("SELECT deleted_token FROM customer WHERE id = ?", String.class, customerId))
                .isEqualTo(String.valueOf(customerId));
    }
}
