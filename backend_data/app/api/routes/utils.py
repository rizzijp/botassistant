import pandas as pd
import re
import time
from fastapi import HTTPException, BackgroundTasks
from sqlalchemy import text
from app.db.connection import engine
from app.core.llm import call_llm
from app.core.audit_log import save_audit_log
from app.semantic.semantic_types import QueryRequest

# --- FUNCIONES AUXILIARES ---

def _validate_security_patterns(sql: str, params: dict = None):
    """
    Validación de Seguridad Profunda.
    1. Estructural: Revisa que sea SELECT y sin inyecciones múltiples.
    2. Contenido: Revisa los parámetros inyectados buscando patrones maliciosos.
    """
    sql_clean = sql.strip().upper()
    
    # 1. Regla de Oro: Solo Lectura
    if not sql_clean.startswith("SELECT"):
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

def _generate_success_message_static(df: pd.DataFrame, viz_type: str, title: str) -> str:
    """
    Genera un mensaje estático (rápido) para cuando se usan REGLAS.
    """
    row_count = len(df)
    if row_count == 0:
        return f"No se encontraron resultados para: {title}."

    if viz_type == "number":
        try:
            valor = df.iloc[0, 0]
            if isinstance(valor, (int, float)):
                valor = f"{valor:,.2f}"
            return f"El resultado para '{title}' es: {valor}."
        except:
            return f"Aquí tienes el resultado para '{title}'."

    if "top" in title.lower():
        top_n = min(3, row_count)
        first_item = df.iloc[0, 0]
        return f"Aquí tienes el Top {row_count} solicitado. Liderando la lista está {first_item}."

    return f"He encontrado {row_count} registros para '{title}'."

def _generate_ai_summary(question: str, df: pd.DataFrame, model: str) -> str:
    """
    Usa el LLM para leer los datos y redactar una respuesta natural.
    Se usa SOLO cuando la consulta pasó por el LLM (Estrategia 2).
    """
    if df.empty:
        return "He realizado la consulta, pero no se encontraron datos que coincidan con tus criterios."

    # Preparamos una muestra de datos para que el LLM los lea
    # Limitamos a 10 filas para no saturar el prompt si hay miles de resultados
    data_preview = df.head(10).to_string(index=False)
    row_count = len(df)
    context_note = f"(Mostrando las primeras 10 filas de {row_count} totales)" if row_count > 10 else ""

    system_prompt = """
    Eres un analista de datos experto. Tu trabajo es explicar los resultados de una consulta en ESPAÑOL natural.
    
    INSTRUCCIONES:
    1. Recibirás la pregunta del usuario y una tabla de datos con la respuesta.
    2. Redacta una respuesta directa y conversacional (ej: "Los empleados con más ventas son...").
    3. Menciona los valores clave o los primeros resultados si es un ranking.
    4. Si hay muchos datos, resume la tendencia general.
    5. NO menciones términos técnicos como "SQL", "query" o "dataframe".
    6. Sé breve y profesional.
    """

    user_prompt = f"""
    PREGUNTA USUARIO: "{question}"
    
    DATOS OBTENIDOS {context_note}:
    {data_preview}
    
    Respuesta sugerida:
    """

    try:
        # Llamada al LLM para "humanizar" el dato
        summary = call_llm(system_prompt, user_prompt, model_alias=model)
        # Limpieza básica por si el LLM pone comillas
        return summary.strip().strip('"')
    except Exception as e:
        print(f"⚠️ Falló el resumen IA: {e}")
        # Fallback si el LLM de resumen falla
        return f"Aquí tienes los {row_count} resultados encontrados para tu consulta."

def _determine_has_graph(viz_type: str, row_count: int) -> bool:
    """
    Lógica para definir 'tiene_grafica'.
    """
    if row_count == 0:
        return False
    
    # Gráficos válidos para visualización
    GRAPH_TYPES = ["bar", "line", "pie", "scatter", "area"]
    
    # Si es 'number' o 'table', NO es gráfica visual
    if viz_type in GRAPH_TYPES:
        return True
    
    return False

def _log_audit(bg_tasks: BackgroundTasks, req: QueryRequest, sql: str, plan: dict, rows: int, time_taken: float, viz: str, error: str = None):
    """Helper para limpiar el código principal de la llamada larguísima a logs."""
    bg_tasks.add_task(
        save_audit_log,
        user_id=req.user_id,
        question=req.question,
        model=plan.get("source", req.model), # Si viene de reglas usa "rules_engine", sino el modelo
        query_plan=plan,
        sql=sql,
        time_taken=time_taken,
        rows=rows,
        error=error,
        viz_type=viz
    )
