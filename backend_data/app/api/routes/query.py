import time
import pandas as pd
import re
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from app.semantic.semantic_types import QueryRequest, QueryResponse
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
from app.semantic.semantic_types import VizType
from app.semantic.rules_engine import check_rules
from app.api.routes.utils import _execute_sql_safe, _generate_success_message_static, _generate_ai_summary, _determine_has_graph, _log_audit



router = APIRouter()

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
    
    print(f"👤 [User {request.user_id}] Pregunta: '{request.message}' | Modelo: {request.model}")

    # =========================================================================
    # INTENTO 1: MOTOR DE REGLAS (Fast Path & Safe Execution) ⚡
    # =========================================================================
    try:
        rule_hit = check_rules(request.message)
        
        if rule_hit:
            print(f"   ⚡ [RULES] Regla encontrada: {rule_hit.get('viz_title')}")

            # Preparar datos candidatos
            sql_candidate = rule_hit["sql"]
            params_candidate = rule_hit.get("params", {}) # <--- Capturamos los params (:p1)
            viz_type_candidate = rule_hit["viz_type"]
            viz_title_candidate = rule_hit["viz_title"]

            # Ejecutamos (Helper encapsula seguridad y conexión)
            df = _execute_sql_safe(sql_candidate, params_candidate)
            
            # Auditoría Exito Reglas
            print(f"   ✅ [RULES SUCCESS] Consulta resuelta por reglas.")
            row_count = len(df)
            elapsed = round(time.time() - start_time, 4)

            # MENSAJE ESTÁTICO (Rules = Velocidad)
            mensaje_final = _generate_success_message_static(df, viz_type_candidate, viz_title_candidate)
            tiene_grafica_bool = _determine_has_graph(viz_type_candidate, row_count)

            query_plan_dict = {
                "source": "rules_engine", 
                "match": "regex",
                "params": str(params_candidate)
            }
            
            #_log_audit(background_tasks, request, sql_candidate, query_plan_dict, row_count, elapsed, viz_type_candidate)
            
            # RETORNO ANTICIPADO: Si esto funciona, NO ejecuta el LLM.
            #return QueryResponse(
            #    user_id=request.user_id,
            #    question=request.question,
            #    sql=sql_candidate,
            #    data=df.to_dict(orient="records"),
            #    columns=list(df.columns),
            #    row_count=row_count,
            #    execution_time=elapsed,
            #    viz_type=viz_type_candidate,
            #    viz_title=viz_title_candidate
            #)
            return QueryResponse(
                exito=True,
                session_id=request.session_id,
                mensaje=mensaje_final,
                sql_generado=sql_candidate,
                datos=df.to_dict(orient="records"),
                columnas=list(df.columns),
                total_filas=row_count,
                tipo_grafica=viz_type_candidate,
                tiene_grafica=tiene_grafica_bool,
                grafica_base64=None
            )

    # =========================================================================
    # INTENTO 2: LLM (Fallback / Slow Path) 🤖
    # =========================================================================

        print(f"   🤖 [LLM START] Generando plan con Inteligencia Artificial...")

        # PASO A: Generar el Plan
        # -------------------------------------------------
        query_plan = generate_query_plan(request.message, llm_model_name=request.model)
        query_plan_dict = query_plan.model_dump() # <--- Guardamos el JSON

        # CAPTURA DEL ESTADO: Si falla en el paso B o C, sabremos el tipo de gráfico.
        viz_type_to_log = query_plan.viz_type
        viz_title_response = query_plan.viz_title or request.question
            
        # PASO B: Compilar a SQL (Lógica Determinista)
        # --------------------------------------------
        generated_sql = compile_sql(query_plan)
        print(f"   📝 SQL Generado: {generated_sql}")
        
        # PASO C: Seguridad y Ejecución en Base de Datos (Acceso a Datos)
        # --------------------------------------------------
        # Ejecutar (Helper encapsula seguridad y conexión)
        # El LLM no usa params externos, pasamos None
        df = _execute_sql_safe(generated_sql, params=None)
        
        row_count = len(df)
        elapsed = round(time.time() - start_time, 4)
        # Generación de respuesta (AHORA CON IA)
        # Le pasamos el DataFrame al LLM para que "lea" los datos y responda
        mensaje_final = _generate_ai_summary(request.message, df, request.model)
        tiene_grafica_bool = _determine_has_graph(viz_type_to_log, row_count)
        

        # PASO D: Auditoría EXITO (En segundo plano)
        #_log_audit(background_tasks, request, generated_sql, query_plan_dict, row_count, elapsed, viz_type_to_log)
            
        # PASO E: Respuesta al Cliente
        #return QueryResponse(
        #    user_id=request.user_id,
        #    question=request.question,
        #    sql=generated_sql,
        #    data=df.to_dict(orient="records"), # Convierte DataFrame a lista de objetos JSON
        #    columns=list(df.columns),
        #    row_count=len(df),
        #    execution_time=elapsed,
        #    viz_type=viz_type_to_log if viz_type_to_log else "table", # Fallback
        #    viz_title=viz_title_response
        #)
        return QueryResponse(
            exito=True,
            session_id=request.session_id,
            mensaje=mensaje_final,
            sql_generado=generated_sql,
            datos=df.to_dict(orient="records"),
            columnas=list(df.columns),
            total_filas=row_count,
            tipo_grafica=viz_type_to_log,
            tiene_grafica=tiene_grafica_bool,
            grafica_base64=None
        )

    except Exception as e:
        # --- BLOQUE DE MANEJO DE ERRORES Y SEGURIDAD ---
        # Cálculo del tiempo hasta el fallo
        elapsed = round(time.time() - start_time, 4)
        error_msg = str(e)

        # Logueamos el error real en consola del servidor
        print(f"❌ ERROR CRÍTICO [User {request.user_id}]: {error_msg}")

        # PASO F: Auditoría ERROR (En segundo plano)
        # Guardamos qué intentó preguntar y por qué falló
        #try:
        #    _log_audit(background_tasks, request, generated_sql, query_plan_dict, 0, elapsed, viz_type_to_log or "error", str(e))
        #except:
        #    print("   ❌ Falló el log de error crítico.")


        # 1. DETECCIÓN DE ATAQUE
        # Revisamos si el error viene de nuestras validaciones de seguridad o si es un HTTPException 400
        is_security_issue = False
        if "SECURITY" in error_msg.upper(): 
            is_security_issue = True
        if isinstance(e, HTTPException) and e.status_code == 400:
            is_security_issue = True

        # 2. LOGGING DIFERENCIADO (Así sabes si bloqueaste un ataque)
        if is_security_issue:
            print(f"   ⛔ [SECURITY BLOCK] Ataque bloqueado: {error_msg}")
            # Aquí podrías guardar un log especial en auditoría con status="BLOCKED"
            status_code = 400
            client_message = f"Solicitud rechazada por seguridad: {error_msg}"
        else:
            print(f"   ❌ [SERVER ERROR] Error: {error_msg}")
            status_code = 500
            client_message = "Lo siento, hubo un error inesperado al procesar tu consulta."

        # Intentamos rescatar qué SQL falló (Reglas o LLM) para mostrarlo si es necesario
        sql_failed = generated_sql if generated_sql else sql_candidate

        # 3. RESPUESTA AL CLIENTE
        return JSONResponse(
            status_code=status_code,
            content={
                "exito": False,
                "session_id": request.session_id,
                "mensaje": client_message,
                "sql_generado": sql_failed,
                "datos": [],
                "columnas": [],
                "total_filas": 0,
                "tipo_grafica": None,
                "tiene_grafica": False,
                "grafica_base64": None
            }
        )