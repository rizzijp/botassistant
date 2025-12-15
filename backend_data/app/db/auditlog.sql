CREATE SCHEMA IF NOT EXISTS audit;
CREATE TABLE audit.logs (
    log_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    user_id INTEGER,
    question TEXT,
    model_used TEXT,
    query_plan JSONB,
    sql_generated TEXT,
    status VARCHAR(50),
    execution_time_sec NUMERIC(10,4),
    row_count INTEGER,
    error_message TEXT,
    viz_type VARCHAR(50)
);