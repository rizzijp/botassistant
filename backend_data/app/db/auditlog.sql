-- 1. CREAR ESQUEMAS
CREATE SCHEMA IF NOT EXISTS audit;

-- 2. TABLA DE AUDITORÍA
DROP TABLE IF EXISTS audit.logs CASCADE;
CREATE TABLE audit.logs (
    log_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    user_id INTEGER,
    session_id VARCHAR(50),
    exito BOOLEAN DEFAULT FALSE,
    mensaje TEXT NOT NULL,
    model_used TEXT,
    sql_generado TEXT,
    execution_time_sec NUMERIC(10,4),
    total_filas INTEGER DEFAULT 0,
    error_message TEXT,
    tipo_grafica VARCHAR(50),
    tiene_grafica BOOLEAN DEFAULT FALSE
);

-- Índice para buscar rápido por usuario o fecha
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit.logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit.logs(timestamp);

