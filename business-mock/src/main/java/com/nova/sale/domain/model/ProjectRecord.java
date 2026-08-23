package com.nova.sale.domain.model;

import java.time.Instant;

public record ProjectRecord(
        String projectId,
        String title,
        String premise,
        String style,
        Instant createdAt,
        Instant updatedAt
) {}
