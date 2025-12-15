import pandas as pd
from sqlalchemy import text
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.db.connection import engine

def build_staging():
    print("🧹 [ETL 2/3] Construyendo CAPA STAGING...")
    
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging;"))

    # --- 1. SALES: Definición Estricta de Tipos ---
    print("   🔧 Tipando SALES...")
    df_sales = pd.read_sql("SELECT * FROM raw.sales", engine)
    
    # DEFINICIÓN DE TIPOS (Esto crea la estructura correcta en Postgres)
    # Fechas
    df_sales['sale_date'] = pd.to_datetime(df_sales[['year', 'month', 'day']])
    df_sales['sale_ts'] = pd.to_datetime(df_sales[['year', 'month', 'day', 'hour']])
    
    # Números (Float para dinero, Int para cantidades)
    df_sales['subtotal'] = pd.to_numeric(df_sales['subtotal'], errors='coerce').fillna(0.0)
    df_sales['total'] = pd.to_numeric(df_sales['total'], errors='coerce').fillna(0.0)
    df_sales['discount_amount'] = pd.to_numeric(df_sales['discount_amount'], errors='coerce').fillna(0.0)
    df_sales['quantity'] = pd.to_numeric(df_sales['quantity'], errors='coerce').fillna(0).astype(int)
    
    # Strings
    df_sales['sales_channel'] = df_sales['sales_channel'].astype(str)
    
    # Subida
    df_sales.to_sql("sales", engine, schema="staging", if_exists="replace", index=False)

    # --- 2. PRODUCTS: Deduplicación ---
    print("   🔧 Deduplicando PRODUCTS...")
    df_prod = pd.read_sql("SELECT * FROM raw.products", engine)
    
    # Lógica de negocio: Unificar productos repetidos
    df_canon = df_prod.groupby('product_id').agg({
        'product_name': lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0],
        'category': lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0],
        'unit_price': 'median' 
    }).reset_index()
    
    df_canon.to_sql("products_canon", engine, schema="staging", if_exists="replace", index=False)

    # --- 3. DIMENSIONES SIMPLES ---
    for tbl in ['customers', 'hr', 'users']:
        print(f"   🔧 Pasando {tbl}...")
        df = pd.read_sql(f"SELECT * FROM raw.{tbl}", engine)
        
        # Normalizar emails
        if 'email' in df.columns: 
            df['email'] = df['email'].str.lower().str.strip()
            
        # --- AGREGADO: Normalizar roles (Vital para seguridad) ---
        if 'role' in df.columns:
            df['role'] = df['role'].str.lower().str.strip()
            
        df.to_sql(tbl, engine, schema="staging", if_exists="replace", index=False)

    print("✅ Capa STAGING completada.")

if __name__ == "__main__":
    build_staging()