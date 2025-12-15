-- 1. CREAR ESQUEMAS
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS curated;
CREATE SCHEMA IF NOT EXISTS audit;

-- 2. TABLA DE AUDITORÍA
DROP TABLE IF EXISTS audit.logs CASCADE;
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

-- (Opcional) Índice para buscar rápido por usuario o fecha
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit.logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit.logs(timestamp);

-- 3. DEFINIR TABLAS RAW (Tipos estrictos, pero sin PKs bloqueantes aún)

-- CUSTOMERS
DROP TABLE IF EXISTS raw.customers CASCADE;
CREATE TABLE raw.customers (
    customer_id INTEGER, -- Sin PK aún por seguridad en carga
    region VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(150)
);

-- HR (Empleados)
DROP TABLE IF EXISTS raw.hr CASCADE;
CREATE TABLE raw.hr (
    employee_id INTEGER,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    position VARCHAR(100),
    department VARCHAR(100),
    salary NUMERIC(12,2)
);

-- PRODUCTS
-- ¡OJO! Aquí sabemos que el CSV trae duplicados de ID. 
-- NO poner PRIMARY KEY aquí o la carga fallará.
DROP TABLE IF EXISTS raw.products CASCADE;
CREATE TABLE raw.products (
    product_id INTEGER,
    product_name VARCHAR(200),
    category VARCHAR(100),
    unit_price NUMERIC(12,2)
);

-- USERS
DROP TABLE IF EXISTS raw.users CASCADE;
CREATE TABLE raw.users (
    user_id INTEGER,
    employee_id INTEGER,
    role VARCHAR(50),
    email VARCHAR(150),
    password VARCHAR(255)
);

-- SALES (La tabla de hechos)
DROP TABLE IF EXISTS raw.sales CASCADE;
CREATE TABLE raw.sales (
    sale_id INTEGER,
    employee_id INTEGER,
    customer_id INTEGER,
    product_id INTEGER,
    sales_channel VARCHAR(50),
    quantity INTEGER,
    discount_percentage NUMERIC(5,2),
    payment_method VARCHAR(50),
    subtotal NUMERIC(12,2),
    discount_amount NUMERIC(12,2),
    total NUMERIC(12,2),
    year INTEGER,
    month INTEGER,
    day INTEGER,
    hour INTEGER
);


-- 3. DEFINIR TABLAS CURATED

-- SALES CURATED 
-- HECHOS: FACT_SALES (Con las fechas nuevas y PK)
DROP TABLE IF EXISTS curated.fact_sales CASCADE;
CREATE TABLE curated.fact_sales (
    sale_id INTEGER PRIMARY KEY, -- ponemos PK
    sale_date DATE,              -- fecha de venta
    sale_ts TIMESTAMP,           -- timestamp de venta
    employee_id INTEGER,
    customer_id INTEGER,
    product_id INTEGER,
    sales_channel VARCHAR(50),
    quantity INTEGER,
    discount_percentage NUMERIC(5,2),
    payment_method VARCHAR(50),
    subtotal NUMERIC(12,2),
    discount_amount NUMERIC(12,2),
    total NUMERIC(12,2),
    year INTEGER,
    month INTEGER,
    day INTEGER,
    hour INTEGER
);

-- DIMENSIÓN: PRODUCT
DROP TABLE IF EXISTS curated.dim_product CASCADE;
CREATE TABLE curated.dim_product (
    product_id INTEGER PRIMARY KEY,
    product_name VARCHAR(200),
    category VARCHAR(100),
    unit_price NUMERIC(12,2)
);

-- DIMENSIÓN: CUSTOMER
DROP TABLE IF EXISTS curated.dim_customer CASCADE;
CREATE TABLE curated.dim_customer (
    customer_id INTEGER PRIMARY KEY,
    region VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(150)
);

-- DIMENSIÓN: EMPLOYEE
DROP TABLE IF EXISTS curated.dim_employee CASCADE;
CREATE TABLE curated.dim_employee (
    employee_id INTEGER PRIMARY KEY,
    first_name VARCHAR(100), 
    last_name VARCHAR(100),
    position VARCHAR(100),
    department VARCHAR(100),
    salary NUMERIC(12,2)
);

-- DIMENSIÓN: USER
DROP TABLE IF EXISTS curated.dim_user CASCADE;
CREATE TABLE curated.dim_user (
    user_id INTEGER PRIMARY KEY,
    employee_id INTEGER,
    role VARCHAR(50),
    email VARCHAR(150)
    -- La password la seguimos ocultando por seguridad básica,
    -- pero el email y rol los dejamos.
);

-- EXTENSIONES
CREATE EXTENSION IF NOT EXISTS unaccent;