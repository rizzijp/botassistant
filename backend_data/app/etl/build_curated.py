import pandas as pd
import sys
import os

# Ajuste de path para encontrar 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.db.connection import engine

def build_curated():
    print("💎 [ETL 3/3] Construyendo CAPA CURATED (Datos Completos)...")
    
    # 1. FACT SALES
    print("   ➡️ Llenando fact_sales...")
    df_sales = pd.read_sql("SELECT * FROM staging.sales", engine)
    df_sales.to_sql("fact_sales", engine, schema="curated", if_exists="append", index=False)

    # 2. DIM PRODUCT
    print("   ➡️ Llenando dim_product...")
    df_prod = pd.read_sql("SELECT * FROM staging.products_canon", engine)
    df_prod.to_sql("dim_product", engine, schema="curated", if_exists="append", index=False)
    
    # 3. DIM CUSTOMER (Clientes con datos personales)
    print("   ➡️ Llenando dim_customer...")
    # Aquí SÍ hay email en customers.csv
    df_cust = pd.read_sql("""
        SELECT customer_id, region, first_name, last_name, email 
        FROM staging.customers
    """, engine)
    df_cust.to_sql("dim_customer", engine, schema="curated", if_exists="append", index=False)

    # 4. DIM EMPLOYEE (RRHH - CORREGIDO: SIN EMAIL)
    print("   ➡️ Llenando dim_employee...")
    # ERROR CORREGIDO: No pedimos 'email' porque no existe en hr.csv
    df_hr = pd.read_sql("""
        SELECT employee_id, department, position, first_name, last_name, salary 
        FROM staging.hr
    """, engine)
    df_hr.to_sql("dim_employee", engine, schema="curated", if_exists="append", index=False)

    # 5. DIM USER (Usuarios y Roles)
    print("   ➡️ Llenando dim_user...")
    # El email de los empleados está AQUÍ
    df_users = pd.read_sql("""
        SELECT user_id, employee_id, role as role_norm, email 
        FROM staging.users
    """, engine)
    # Renombramos role_norm a role para que coincida con SQL
    df_users = df_users.rename(columns={"role_norm": "role"})
    df_users.to_sql("dim_user", engine, schema="curated", if_exists="append", index=False)
    
    print("✅ ¡Modelo Estrella completo (con datos sensibles disponibles para Admin)!")

if __name__ == "__main__":
    build_curated()