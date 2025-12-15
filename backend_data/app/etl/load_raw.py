import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.db.connection import engine 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data_raw")

def load_raw():
    print("⬇️ [ETL 1/3] Cargando CAPA RAW (Modo Append)...")
    
    csv_files = {
        "customers.csv": "customers",
        "hr.csv": "hr",
        "products.csv": "products",
        "sales.csv": "sales",
        "users.csv": "users"
    }

    for file_name, table_name in csv_files.items():
        file_path = os.path.join(RAW_DATA_DIR, file_name)
        if os.path.exists(file_path):
            print(f"   📄 Leyendo {file_name}...")
            df = pd.read_csv(file_path)
            
            # Limpieza de nombres de columnas para coincidir con SQL
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            
            # ¡EL CAMBIO CLAVE!
            # if_exists='append': Inserta datos en la tabla que YA creamos con init_db.sql
            # index=False: No intentes subir el índice de pandas como columna
            try:
                df.to_sql(table_name, engine, schema="raw", if_exists="append", index=False)
                print(f"      ✅ Insertadas {len(df)} filas en raw.{table_name}")
            except Exception as e:
                print(f"      ❌ ERROR cargando {table_name}: {e}")
        else:
            print(f"   ⚠️ ALERTA: No encuentro {file_name}")

    print("🏁 Carga RAW finalizada.")

if __name__ == "__main__":
    load_raw()