CREATE TABLE IF NOT EXISTS project (
    project_id VARCHAR(128) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    premise TEXT NOT NULL,
    style_code VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
