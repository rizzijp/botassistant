import os
import sys
from sqlalchemy import text

# Ajuste de path para encontrar 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.db.connection import engine

def init_db():
    print("🏗️  [DB] Inicializando esquemas y tablas vacías...")
    
    # Ruta al archivo SQL
    sql_path = os.path.join(os.path.dirname(__file__), "init_db.sql")
    
    with open(sql_path, "r", encoding="utf-8") as f:
        sql_script = f.read()
    
    # Ejecutamos el SQL completo
    with engine.begin() as conn:
        # SQLAlchemy a veces se queja con scripts largos, lo dividimos por ; si es necesario, 
        # pero text() suele manejarlo bien en bloques.
        conn.execute(text(sql_script))
        
    print("✅ [DB] Estructura creada en Neon correctamente (Tablas vacías con tipos definidos).")

if __name__ == "__main__":
    init_db()