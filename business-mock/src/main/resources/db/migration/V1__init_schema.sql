-- M1 业务数据域：employee / customer / follow_up / purchase
-- 约定：BIGINT 主键、utf8mb4、DATETIME(3)、VARCHAR+CHECK 枚举、客户/员工软删除 deleted_token

CREATE TABLE IF NOT EXISTS employee (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    name VARCHAR(64) NOT NULL,
    role VARCHAR(16) NOT NULL,
    phone VARCHAR(32) NULL,
    deleted_token CHAR(1) NOT NULL DEFAULT '0',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT uk_employee_username UNIQUE (username, deleted_token),
    CONSTRAINT ck_employee_role CHECK (role IN ('employee', 'manager'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS customer (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    name VARCHAR(64) NOT NULL,
    phone VARCHAR(32) NULL,
    gender CHAR(1) NOT NULL DEFAULT 'U',
    lifecycle_stage VARCHAR(16) NOT NULL DEFAULT 'new',
    source VARCHAR(64) NULL,
    remark VARCHAR(512) NULL,
    deleted_token CHAR(1) NOT NULL DEFAULT '0',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_customer_owner FOREIGN KEY (owner_id) REFERENCES employee (id),
    CONSTRAINT ck_customer_gender CHECK (gender IN ('M', 'F', 'U')),
    CONSTRAINT ck_customer_stage CHECK (lifecycle_stage IN ('new', 'prospective', 'existing', 'churn_risk'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_customer_owner ON customer (owner_id);

CREATE TABLE IF NOT EXISTS follow_up (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    employee_id BIGINT NOT NULL,
    channel VARCHAR(16) NOT NULL DEFAULT 'chat',
    content TEXT NOT NULL,
    next_follow_at DATETIME(3) NULL,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_follow_up_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT fk_follow_up_employee FOREIGN KEY (employee_id) REFERENCES employee (id),
    CONSTRAINT ck_follow_up_channel CHECK (channel IN ('chat', 'phone', 'visit', 'wechat'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_follow_up_customer ON follow_up (customer_id);

CREATE TABLE IF NOT EXISTS purchase (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    product_name VARCHAR(128) NOT NULL,
    category VARCHAR(64) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    purchased_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    remark VARCHAR(512) NULL,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_purchase_customer FOREIGN KEY (customer_id) REFERENCES customer (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_purchase_customer ON purchase (customer_id);
