import sys
import os
from sqlalchemy import text

# Ajuste de path para encontrar 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.connection import engine

def apply_constraints():
    print("🔐 APLICANDO INTEGRIDAD REFERENCIAL (Foreign Keys)...")
    
    queries = [
        # 1. Relación Ventas -> Productos
        """
        ALTER TABLE curated.fact_sales 
        ADD CONSTRAINT fk_sales_product 
        FOREIGN KEY (product_id) REFERENCES curated.dim_product(product_id);
        """,
        
        # 2. Relación Ventas -> Clientes
        """
        ALTER TABLE curated.fact_sales 
        ADD CONSTRAINT fk_sales_customer 
        FOREIGN KEY (customer_id) REFERENCES curated.dim_customer(customer_id);
        """,
        
        # 3. Relación Ventas -> Empleados
        """
        ALTER TABLE curated.fact_sales 
        ADD CONSTRAINT fk_sales_employee 
        FOREIGN KEY (employee_id) REFERENCES curated.dim_employee(employee_id);
        """
        # Nota: No unimos con dim_user porque no todas las ventas tienen usuario de sistema,
        # pero sí todas tienen empleado.
    ]

    with engine.begin() as conn:
        for sql in queries:
            try:
                # Intentamos crear la FK. Si ya existe, fallará y lo ignoramos.
                conn.execute(text(sql))
                print("   ✅ Foreign Key aplicada exitosamente.")
            except Exception as e:
                if "already exists" in str(e):
                    print("   ℹ️  La Foreign Key ya existía (omitida).")
                else:
                    print(f"   ❌ ERROR aplicando FK: {e}")
                    print("      (Esto suele pasar si hay datos huérfanos. Corre verify_etl.py)")

    print("\n🏁 Base de Datos Blindada. Ahora Neon garantiza la integridad.")

if __name__ == "__main__":
    apply_constraints()