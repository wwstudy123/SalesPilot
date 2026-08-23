-- M4 画像域：customer_profile_field（画像字段级版本与依据）+ approval（审批凭证）
-- 约定继承 V1：BIGINT 主键、utf8mb4、DATETIME(3)、VARCHAR+CHECK 枚举、索引内联

CREATE TABLE IF NOT EXISTS customer_profile_field (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    field_key VARCHAR(32) NOT NULL,
    field_value VARCHAR(1024) NOT NULL,
    evidence VARCHAR(512) NOT NULL,
    version INT NOT NULL DEFAULT 1,
    updated_by BIGINT NULL,
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_profile_field_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT uk_profile_field UNIQUE (customer_id, field_key),
    INDEX idx_profile_field_customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS approval (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    token CHAR(32) NOT NULL,
    tool VARCHAR(64) NOT NULL,
    actor_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    payload JSON NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    expires_at DATETIME(3) NOT NULL,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    consumed_at DATETIME(3) NULL,
    CONSTRAINT uk_approval_token UNIQUE (token),
    CONSTRAINT uk_approval_idempotency UNIQUE (idempotency_key),
    CONSTRAINT ck_approval_status CHECK (status IN ('pending', 'consumed', 'expired', 'rejected')),
    INDEX idx_approval_customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
