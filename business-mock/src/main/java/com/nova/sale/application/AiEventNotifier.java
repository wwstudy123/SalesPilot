package com.nova.sale.application;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 业务事件通知器（架构 §3.3 的 MVP 简化形态）：
 * 跟进记录落库后异步通知 sale-agent 触发 Profile 增量抽取。
 * 正式版为 outbox + Redis Stream；演示期直连 HTTP，失败仅记日志不影响主链路。
 */
@Component
public class AiEventNotifier {
    private static final Logger log = LoggerFactory.getLogger(AiEventNotifier.class);

    private final RestClient restClient;
    private final ExecutorService executor = Executors.newSingleThreadExecutor(runnable -> {
        Thread thread = new Thread(runnable, "ai-event-notifier");
        thread.setDaemon(true);
        return thread;
    });

    public AiEventNotifier(@Value("${sale.internal-api-base-url:http://127.0.0.1:8000}") String baseUrl) {
        this.restClient = RestClient.builder().baseUrl(baseUrl).build();
    }

    public void followUpCreated(Long followUpId, Long customerId, Long employeeId, String jwt) {
        executor.submit(() -> {
            try {
                java.util.HashMap<String, Object> body = new java.util.HashMap<>(Map.of(
                        "event", "follow_up.created",
                        "follow_up_id", followUpId,
                        "customer_id", customerId,
                        "employee_id", employeeId
                ));
                if (jwt != null && !jwt.isBlank()) {
                    body.put("jwt", jwt);
                }
                restClient.post()
                        .uri("/api/ai/events/follow_up_created")
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(body)
                        .retrieve()
                        .toBodilessEntity();
                log.info("ai event notified: follow_up.created followUpId={}", followUpId);
            } catch (Exception ex) {
                log.warn("ai event notify failed (non-fatal): followUpId={} error={}", followUpId, ex.getMessage());
            }
        });
    }
}
