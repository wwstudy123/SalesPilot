-- M6 标签域：字典为准，客户标签可由 HITL 确认后覆盖保存。
CREATE TABLE IF NOT EXISTS tag_dict (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tag_key VARCHAR(64) NOT NULL,
    tag_name VARCHAR(64) NOT NULL,
    tag_type VARCHAR(32) NOT NULL,
    description VARCHAR(512) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uk_tag_dict_key UNIQUE (tag_key),
    CONSTRAINT ck_tag_type CHECK (tag_type IN ('lifecycle', 'preference', 'risk', 'value'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS customer_tag (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    tag_id BIGINT NOT NULL,
    evidence VARCHAR(512) NOT NULL,
    confidence DECIMAL(4, 3) NOT NULL DEFAULT 1.000,
    updated_by BIGINT NULL,
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_customer_tag_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT fk_customer_tag_dict FOREIGN KEY (tag_id) REFERENCES tag_dict (id),
    CONSTRAINT uk_customer_tag UNIQUE (customer_id, tag_id),
    INDEX idx_customer_tag_customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO tag_dict (tag_key, tag_name, tag_type, description) VALUES
    ('lifecycle_new', '新客', 'lifecycle', '尚未完成有效需求沟通的客户'),
    ('lifecycle_prospective', '意向客户', 'lifecycle', '已有明确需求或购买意向'),
    ('lifecycle_existing', '老客户', 'lifecycle', '已购买且可持续服务的客户'),
    ('risk_churn', '流失风险', 'risk', '近期消极反馈或长期未跟进'),
    ('preference_price_sensitive', '价格敏感', 'preference', '对价格、预算或优惠高度关注'),
    ('value_high', '高价值', 'value', '消费能力或累计价值较高')
ON DUPLICATE KEY UPDATE tag_name = VALUES(tag_name), description = VALUES(description), active = TRUE;
