import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.init_db import init_db       # <--- Crea las tablas primero
from app.etl.load_raw import load_raw
from app.etl.build_staging import build_staging
from app.etl.build_curated import build_curated
# Como apply_constraints.py está en la misma carpeta 'scripts', podemos importarlo así:
try:
    from scripts.apply_constraints import apply_constraints
except ImportError:
    # Si falla la importación relativa, intentamos importación directa
    from apply_constraints import apply_constraints


def main():
    print("🚀 INICIANDO PIPELINE PROFESIONAL...")
    try:
        # 1. Definir Estructura (DDL)
        # Borra tablas viejas y crea las nuevas vacías
        init_db()
        
        # 2. Cargar Datos (ETL)
        load_raw()       # CSV -> Raw
        build_staging()  # Raw -> Staging (Limpieza)
        build_curated()  # Staging -> Curated (Modelo Estrella)

        # PASO 3: Integridad (Constraints)
        # --------------------------------
        # Aplicamos las FKs al final para asegurar la calidad
        print("\n🔐 [AUTOMATIZACIÓN] Aplicando reglas de integridad...")
        apply_constraints()
        
        print("\n✨ ¡SISTEMA REPLEGADO CON ÉXITO!")
        print("   Tus datos en Neon están limpios, transformados y blindados.")
        
    except Exception as e:
        print(f"\n❌ ERROR FATAL EN EL PIPELINE: {e}")


if __name__ == "__main__":
    main()