import time
import pandas as pd
import re
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from app.api.models.api_models import QueryRequest, QueryResponse
# Importamos los modelos Pydantic (Request/Response)
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from app.db.connection import engine
from app.semantic.router import generate_query_plan
from app.semantic.compiler import compile_sql
from app.core.audit_log import save_audit_log
from app.core.config import MODELO_PRINCIPAL
from app.core.llm import call_llm
from app.semantic.models.query_plan import VizType
from app.semantic.rules_engine import check_rules
import logging
from app.api.services.sql_executor import _execute_sql_safe  
from app.api.services.response_builder import (
    _build_response,
    _generate_success_message_static,
    _generate_ai_summary,
    _determine_has_graph,
    _log_audit
)
from app.api.services.sql_debugger import fix_sql_with_llm


router = APIRouter()
logger = logging.getLogger(__name__)

def _try_rules_engine(request, start_time, background_tasks) -> Optional[QueryResponse]:
    """
    Intenta resolver la duda usando reglas predefinidas.
    Maneja dos caminos: 
    A) Respuesta Estática (Saludo) -> Sin SQL, Sin Datos.
    B) Respuesta de Datos (Ventas) -> Con SQL, Con Datos y Agente interpretador.
    """
    rule_hit = check_rules(request.message)
    if not rule_hit:
        return None
    
    logger.info(f"   ⚡ [RULES] Regla encontrada: {rule_hit.get('viz_title')}")

    # =========================================================================
    # CAMINO A: RESPUESTA ESTÁTICA
    # =========================================================================
    static_msg = rule_hit.get("static_message")
    
    if static_msg:
        elapsed = round(time.time() - start_time, 4)
        logger.info(f"   ✅ [CHAT MODE] Respondiendo saludo/ayuda.")

        # Auditoría limpia (sin error)
        _log_audit(
            bg_tasks=background_tasks,
            req=request,
            sql=None, # No guardamos SQL basura
            model_used="rules_engine",
            rows=0,
            time_taken=elapsed,
            viz="text",
            error=None,
            tiene_grafica=False
        )

        # RETORNO LIMPIO (Lo que pediste)
        return _build_response(
            request=request,
            df=pd.DataFrame(),  # -> Se convierte en "datos": []
            sql=None,           # -> Se convierte en "sql_generado": null
            viz_type="text",
            elapsed=elapsed,
            message=static_msg, # -> "¡Hola! Soy tu asistente..." (Sin prefijos)
            tiene_grafica=False,
            viz_title=None,
            grafica_base64=None,
            motor="rules"
        )

    # =========================================================================
    # CAMINO B: RESPUESTA ANALÍTICA (Tu Caso 2 - El resto)
    # =========================================================================
    # Aquí SÍ actúa el agente de datos, ejecuta SQL y devuelve filas.

    # Preparar datos candidatos
    sql_raw = rule_hit["sql"] # borrar luego de testear
    sql_candidate = f"/* ⚡ REGLA */ {sql_raw}" # borrar luego de testear
    #sql_candidate = rule_hit["sql"]
    params_candidate = rule_hit.get("params", {}) # <--- Capturamos los params (:p1)
    viz_type_candidate = rule_hit["viz_type"]
    viz_title_candidate = rule_hit["viz_title"]
    
    # Ejecutamos (Helper encapsula seguridad y conexión)
    df = _execute_sql_safe(sql_candidate, params_candidate)
    
    # Auditoría Exito Reglas
    logger.info(f"   ✅ [RULES SUCCESS] Consulta resuelta por reglas.")
    row_count = len(df)
    elapsed = round(time.time() - start_time, 4)
    
    # MENSAJE ESTÁTICO (Rules = Velocidad)
    mensaje_final = _generate_success_message_static(df, viz_type_candidate, viz_title_candidate)
    tiene_grafica_bool = _determine_has_graph(viz_type_candidate, row_count)

    _log_audit(
        bg_tasks=background_tasks,
        req=request,
        sql=sql_candidate,
        model_used="rules_engine",
        rows=row_count,
        time_taken=elapsed,
        viz=viz_type_candidate,
        error=None,
        tiene_grafica=tiene_grafica_bool
    )
    
    # RETORNO ANTICIPADO: Si esto funciona, NO ejecuta el LLM.
    return _build_response(
        request=request,
        df=df,
        sql=sql_candidate,
        viz_type=viz_type_candidate,
        elapsed=elapsed,
        message=mensaje_final,
        tiene_grafica=tiene_grafica_bool,
        viz_title=viz_title_candidate,
        grafica_base64=None
    )

def _try_llm_engine(request, start_time, background_tasks) -> QueryResponse:
    """Fallback to LLM query planning."""
    model_to_use = request.model or MODELO_PRINCIPAL
    logger.info(f"   🤖 [LLM START] Generando plan con LLM {model_to_use}")

    # PASO A: Generar el Plan
    query_plan = generate_query_plan(request.message, llm_model_name=model_to_use)
    #query_plan_dict = query_plan.model_dump() # <--- Guardamos el JSON

    # CAPTURA DEL ESTADO: Si falla en el paso B o C, sabremos el tipo de gráfico.
    viz_type_to_log = query_plan.viz_type
    viz_title_response = query_plan.viz_title or request.message

    # PASO B: Compilar a SQL (Lógica Determinista)
    # --------------------------------------------
    generated_sql = compile_sql(query_plan)
    logger.info(f"SQL Generado: {generated_sql}")

    # PASO C: Seguridad y Ejecución en Base de Datos (Acceso a Datos)
    # --- BLOQUE DE EJECUCIÓN CON SELF-HEALING (Refactorizado) ---
    try:
        # Intento 1: Ejecución normal
        # El LLM no usa params externos, pasamos None
        logger.info(f"   🏗️ [EXECUTE] Intento 1: Ejecución normal")
        df = _execute_sql_safe(generated_sql, params=None)
    except Exception as e:
        error_msg = str(e)
    
    # Si es un error de seguridad (DROP, DELETE), NO reparamos. Abortamos.
        if "SECURITY" in error_msg:
            raise e
    
    # Si es error de SQL (sintaxis/columnas), llamamos al Agente Debugger
        logger.info(f"   🔧 Fallo SQL. Llamando al agente SQL Debugger...")
    
    # 1. El Agente intenta arreglarlo
        fixed_sql = fix_sql_with_llm(generated_sql, error_msg, model_to_use)
        logger.info(f"   ✨ SQL Reparado: {fixed_sql}")
    
    # 2. Reintentamos con la cura
        try:
            generated_sql = fixed_sql # Actualizamos para que salga bien en el log/respuesta
            df = _execute_sql_safe(fixed_sql, params=None)
            logger.info("   ✅ Reparación exitosa. Query ejecutada.")
        except Exception as e2:
            logger.error("   ❌ La reparación falló.")
            raise e2 # Lanzamos el error original al usuario

    row_count = len(df)
    elapsed = round(time.time() - start_time, 4)
    # Generación de respuesta (AHORA CON IA)
    # Le pasamos el DataFrame al LLM para que "lea" los datos y responda
    mensaje_final = _generate_ai_summary(request.message, df, model_to_use)
    tiene_grafica_bool = _determine_has_graph(viz_type_to_log, row_count)
            

    # PASO D: Auditoría EXITO (En segundo plano)
    _log_audit(
        bg_tasks=background_tasks,
        req=request,
        sql=generated_sql,
        model_used=model_to_use,
        rows=row_count,
        time_taken=elapsed,
        viz=viz_type_to_log,
        error=None,
        tiene_grafica=tiene_grafica_bool
    )
    
    # PASO E: Respuesta al Cliente
    return _build_response(
        request=request,
        df=df,
        sql=generated_sql,
        viz_type=viz_type_to_log,
        viz_title=viz_title_response,
        elapsed=elapsed,
        message=mensaje_final,
        tiene_grafica=tiene_grafica_bool,
        grafica_base64=None
    )

def _handle_query_error(e, request, start_time, background_tasks, sql=None, model_used=None, viz=None):
    """Centralized error handling."""
    # --- BLOQUE DE MANEJO DE ERRORES Y SEGURIDAD ---
    # Cálculo del tiempo hasta el fallo
    elapsed = round(time.time() - start_time, 4)
    error_msg = str(e)

    # Logueamos el error real en consola del servidor
    logger.error(f"ERROR CRÍTICO [User {request.user_id}]: {error_msg}")

    # PASO F: Auditoría ERROR (En segundo plano)
    # Guardamos qué intentó preguntar y por qué falló
    # Si no sabemos qué modelo falló, usamos el que pidió el request por defecto
    modelo_final = model_used or request.model

    try:
        _log_audit(
            bg_tasks=background_tasks,
            req=request,
            sql=sql,
            model_used=modelo_final,
            rows=0,
            time_taken=elapsed,
            viz=viz or "error",
            error=str(e),
            tiene_grafica=False
        )
    except Exception as log_err:
        logger.error(f"   ❌ Falló el log de error crítico: {log_err}")


    # 1. DETECCIÓN DE ATAQUE
    # Revisamos si el error viene de nuestras validaciones de seguridad o si es un HTTPException 400
    is_security_issue = False
    if "SECURITY" in error_msg.upper(): 
        is_security_issue = True
    if isinstance(e, HTTPException) and e.status_code == 400:
        is_security_issue = True

    # 2. LOGGING DIFERENCIADO (Así sabes si bloqueaste un ataque)
    if is_security_issue:
        logger.error(f"   ⛔ [SECURITY BLOCK] Ataque bloqueado: {error_msg}")
        # Aquí podrías guardar un log especial en auditoría con status="BLOCKED"
        status_code = 400
        client_message = f"Solicitud rechazada por seguridad: {error_msg}"
    else:
        logger.error(f"Critical error: {e}", exc_info=True)
        status_code = 500
        client_message = "Lo siento, hubo un error inesperado al procesar tu consulta."

    # Intentamos rescatar qué SQL falló (Reglas o LLM) para mostrarlo si es necesario
    #sql_failed = generated_sql if generated_sql else sql_candidate

    # 3. RESPUESTA AL CLIENTE
    return JSONResponse(
        status_code=status_code,
        content={
            "exito": False,
            "session_id": request.session_id,
            "mensaje": client_message,
            "sql_generado": None,
            "datos": [],
            "columnas": [],
            "total_filas": 0,
            "tipo_grafica": None,
            "tiene_grafica": False,
            "grafica_base64": None
        }
    )

# --- API ENDPOINT ---

@router.post("/ask", response_model=QueryResponse)
async def ask_database(request: QueryRequest, background_tasks: BackgroundTasks):
    start_time = time.time()

    # Validación manual para devolver 400 con el formato exacto si el mensaje está vacío
    if not request.message or not request.message.strip():
        return JSONResponse(
            status_code=400,
            content={
                "exito": False,
                "session_id": request.session_id,
                "mensaje": "El campo 'message' es obligatorio y no puede estar vacío",
                "sql_generado": None,
                "datos": [],
                "columnas": [],
                "total_filas": 0,
                "tipo_grafica": None,
                "tiene_grafica": False,
                "grafica_base64": None
            }
        )

    # --- INICIALIZACIÓN SEGURA (State Tracking) ---
    # Variables iniciales (para tener algo que loguear si falla al principio)
    generated_sql = None
    query_plan_dict = {}
    row_count = 0
    # Variables LLM
    viz_type_to_log = None
    viz_title_response = None
    # Variables Reglas
    sql_candidate = None
    params_candidate = {}
    viz_type_candidate = None
    viz_title_candidate = None
    
    logger.info(f"User {request.user_id} | Question: '{request.message}'")

    
    try:
        # INTENTO 1: MOTOR DE REGLAS (Fast Path & Safe Execution) ⚡
        response = _try_rules_engine(request, start_time, background_tasks)
        if response:
            return response
      
        
        # INTENTO 2: LLM (Fallback / Slow Path) 🤖
        return _try_llm_engine(request, start_time, background_tasks)

    except Exception as e:
        return _handle_query_error(
            e, request, start_time, background_tasks,
            sql=generated_sql,
            model_used=request.model,
            viz=viz_type_to_log)