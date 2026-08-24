-- M7 管理域：客户移交保留可审计事件。
CREATE TABLE IF NOT EXISTS customer_transfer_audit (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    from_employee_id BIGINT NOT NULL,
    to_employee_id BIGINT NOT NULL,
    operator_id BIGINT NOT NULL,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_transfer_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT fk_transfer_from_employee FOREIGN KEY (from_employee_id) REFERENCES employee (id),
    CONSTRAINT fk_transfer_to_employee FOREIGN KEY (to_employee_id) REFERENCES employee (id),
    CONSTRAINT fk_transfer_operator FOREIGN KEY (operator_id) REFERENCES employee (id),
    INDEX idx_transfer_customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
