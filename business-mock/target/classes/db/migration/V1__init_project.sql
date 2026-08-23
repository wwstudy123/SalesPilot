-- 示例实体表（M1 起替换为 employee/customer/follow_up 等业务域表）
CREATE TABLE IF NOT EXISTS project (
    project_id VARCHAR(128) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    premise TEXT NOT NULL,
    style_code VARCHAR(64) NOT NULL,
    created_at DATETIME(3) NOT NULL,
    updated_at DATETIME(3) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
