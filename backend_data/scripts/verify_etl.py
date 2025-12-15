import sys
import os
import pandas as pd
from sqlalchemy import text

# Ajuste de path para encontrar 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.connection import engine

def verify_etl():
    print("🕵️ INICIANDO AUDITORÍA DE DATOS EN NEON...\n")
    
    with engine.connect() as conn:
        # 1. VERIFICAR PRODUCTOS (¿Funcionó la limpieza?)
        # -----------------------------------------------
        raw_count = conn.execute(text("SELECT COUNT(*) FROM raw.products")).scalar()
        staging_count = conn.execute(text("SELECT COUNT(*) FROM staging.products_canon")).scalar()
        
        print(f"📦 PRODUCTOS:")
        print(f"   - Filas en RAW (Lo que subiste):     {raw_count}")
        print(f"   - Filas en STAGING (Deduplicados):   {staging_count}")
        
        if raw_count == staging_count:
            print("   ✅ CORRECTO: No hubo pérdida de datos (cada ID era único).")
        else:
            print(f"   ⚠️ ATENCIÓN: Se eliminaron {raw_count - staging_count} duplicados.")

        # Ver una muestra para asegurar que no se llaman "Producto"
        sample = pd.read_sql("SELECT product_id, product_name, unit_price FROM staging.products_canon LIMIT 3", conn)
        print("\n   🔍 Muestra de productos reales:")
        print(sample.to_string(index=False))

        # 2. VERIFICAR VENTAS (¿Están los montos bien?)
        # ---------------------------------------------
        sales_count = conn.execute(text("SELECT COUNT(*) FROM curated.fact_sales")).scalar()
        print(f"\n💰 VENTAS (Curated):")
        print(f"   - Total de transacciones: {sales_count}")
        
        # Verificar integridad: ¿Hay ventas huérfanas?
        # Buscamos ventas cuyo product_id NO exista en la tabla de productos
        orphans = conn.execute(text("""
            SELECT COUNT(*) 
            FROM curated.fact_sales f
            LEFT JOIN curated.dim_product p ON f.product_id = p.product_id
            WHERE p.product_id IS NULL
        """)).scalar()
        
        if orphans == 0:
            print("   ✅ INTEGRIDAD PERFECTA: Todas las ventas apuntan a un producto válido.")
        else:
            print(f"   ❌ GRAVE: Hay {orphans} ventas que apuntan a productos inexistentes.")

        # 3. VERIFICAR CLIENTES Y EMPLEADOS
        # ---------------------------------
        cust_count = conn.execute(text("SELECT COUNT(*) FROM curated.dim_customer")).scalar()
        emp_count = conn.execute(text("SELECT COUNT(*) FROM curated.dim_employee")).scalar()
        print(f"\n👥 DIMENSIONES:")
        print(f"   - Clientes:  {cust_count}")
        print(f"   - Empleados: {emp_count}")

    print("\n🏁 Auditoría finalizada.")

if __name__ == "__main__":
    verify_etl()