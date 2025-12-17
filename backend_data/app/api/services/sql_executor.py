import pandas as pd
import re
import time
from fastapi import HTTPException, BackgroundTasks
from sqlalchemy import text
from app.db.connection import engine
from app.core.llm import call_llm
from app.core.audit_log import save_audit_log
from app.api.models.api_models import QueryRequest


def _validate_security_patterns(sql: str, params: dict = None):
    """
    Validación de Seguridad Profunda.
    1. Estructural: Revisa que sea SELECT y sin inyecciones múltiples.
    2. Contenido: Revisa los parámetros inyectados buscando patrones maliciosos.
    """
    # --- FIX: Limpiar comentarios /* ... */ antes de validar ---
    # Usamos re.DOTALL para que elimine comentarios multilínea si los hubiera
    sql_clean = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL).strip().upper()
    
    # 1. Regla de Oro: Solo Lectura
    # Ahora sí funcionará porque sql_clean empezará con SELECT
    if not sql_clean.startswith("SELECT") and not sql_clean.startswith("WITH"):
        raise HTTPException(status_code=400, detail="SECURITY_VIOLATION: Solo se permiten consultas SELECT.")

    # 2. Regla de Estructura: Inyección múltiple en el SQL crudo
    # (Esto atrapa si el LLM alucina y pone un ; DROP)
    if ";" in sql.strip()[:-1]:
        raise HTTPException(status_code=400, detail="SECURITY_VIOLATION: Inyección SQL detectada (Múltiples sentencias).")

    # 3. Regla de Contenido (NUEVO): Escanear parámetros maliciosos
    # Aunque usemos binding parameters, queremos BLOQUEAR la intención de ataque.
    if params:
        # Patrón: Punto y coma seguido de verbos destructivos (DROP, DELETE, UPDATE, INSERT, ALTER)
        # \s* permite espacios, \b asegura palabra completa.
        dangerous_pattern = re.compile(r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE)\b", re.IGNORECASE)
        
        for key, value in params.items():
            val_str = str(value)
            if dangerous_pattern.search(val_str):
                raise HTTPException(
                    status_code=400, 
                    detail=f"SECURITY_ALERT: Se detectó sintaxis peligrosa en el parámetro '{key}'. Intento de ataque bloqueado."
                )


def _execute_sql_safe(sql: str, params: dict = None) -> pd.DataFrame:
    """
    Validación robusta usando EXPLAIN sobre conexión cruda para soportar
    parámetros estilo pyformat (%(name)s) y evitar errores de SQLAlchemy.
    """
    # 1. Validación de Patrones (Regex)
    _validate_security_patterns(sql, params)
    
    # 2. Validación de Sintaxis (Dry Run con EXPLAIN)
    # Usamos raw_connection para evitar conflictos de sintaxis de parámetros entre SQLAlchemy y Psycopg
    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        # Inyectamos el EXPLAIN directo en el driver
        # Nota: Psycopg maneja la interpolación de params de forma segura aquí
        explain_sql = f"EXPLAIN {sql}"
        
        if params:
            cursor.execute(explain_sql, params)
        else:
            cursor.execute(explain_sql)
            
        # Si no falla, la query es válida. Cerramos cursor.
        cursor.close()
            
    except Exception as e:
        print(f"❌ [VALIDATION FAIL] SQL Inválido: {e}")
        # Limpiamos el mensaje de error
        error_msg = str(e).split('\n')[0] 
        raise HTTPException(500, detail=f"SQL_VALIDATION_ERROR: {error_msg}")
    finally:
        raw_conn.close()

    # 3. Ejecución Real (Pandas + SQLAlchemy)
    # Usamos Pandas para traer los datos formateados
    with engine.connect() as conn:
        # Convertimos params a tuplas/dict según lo que pida SQLAlchemy si es necesario,
        # pero pd.read_sql suele manejar dicts bien con el driver de postgres.
        if params:
            return pd.read_sql(sql, conn, params=params)
        else:
            return pd.read_sql(sql, conn)