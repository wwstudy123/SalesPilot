package com.nova.sagt.domain.model;

import java.time.Instant;

public record ProjectRecord(
        String projectId,
        String title,
        String premise,
        String style,
        Instant createdAt,
        Instant updatedAt
) {}
