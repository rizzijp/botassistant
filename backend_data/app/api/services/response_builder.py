import pandas as pd
import re
import time
from fastapi import HTTPException, BackgroundTasks
from sqlalchemy import text
from app.db.connection import engine
from app.core.llm import call_llm
from app.core.audit_log import save_audit_log
from app.api.models.api_models import QueryRequest
from app.api.models.api_models import QueryResponse

def _build_response(request, df, sql, viz_type, elapsed, message, tiene_grafica, viz_title=None, grafica_base64=None):
    """Build standardized QueryResponse."""
    if not message:
        message = _generate_success_message_static(df, viz_type, viz_title)
    
    return QueryResponse(
        exito=True,
        session_id=request.session_id,
        mensaje=message,
        sql_generado=sql,
        datos=df.to_dict(orient="records"),
        columnas=list(df.columns),
        total_filas=len(df),
        tipo_grafica=viz_type,
        tiene_grafica=tiene_grafica,
        grafica_base64=grafica_base64
    )

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
    3. Menciona los valores clave o los primeros resultados si es un ranking(top 3 como máximo).
    4. Si hay muchos datos, resume la tendencia general.
    5. NO repitas información - di cada cosa UNA SOLA VEZ.
    6. NO menciones términos técnicos como "SQL", "query" o "dataframe".
    7. Sé breve y profesional.
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
        logger.warning(f"Fallo resumen IA: {e}")
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
