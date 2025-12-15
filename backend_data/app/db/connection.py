# backend_data/app/db/connection.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from pathlib import Path

# Cargar variables de entorno del archivo .env
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Obtener la URL de conexión
DATABASE_URL = os.getenv("DATABASE_URL_ADMIN")

if not DATABASE_URL:
    raise ValueError("❌ Error: No se encontró DATABASE_URL_ADMIN en el archivo .env")

# Crear el motor de conexión (Engine)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # recomendado para DB remota
    future=True,
    connect_args={"sslmode": "require"}
)

# Crear una sesión local para interactuar con la BBDD
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para los modelos ORM
Base = declarative_base()

# Función de utilidad para obtener la sesión en otros scripts
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()