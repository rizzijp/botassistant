import time
import pandas as pd
import re
from fastapi import APIRouter, HTTPException, BackgroundTasks
# Importamos los modelos Pydantic (Request/Response)
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from app.db.connection import engine
from app.semantic.router import generate_query_plan
from app.semantic.compiler import compile_sql
from app.core.audit_log import save_audit_log
from app.core.config import MODELO_PRINCIPAL
from app.semantic.semantic_types import VizType
from app.semantic.rules_engine import check_rules



router = APIRouter()

# --- 1. MODELOS DE DATOS (DTOs) ---
# Definimos estrictamente qué entra y qué sale de la API.

class QueryRequest(BaseModel):
    user_id: int = Field(..., description="ID del usuario que hace la consulta (para auditoría)")
    question: str = Field(..., description="La pregunta en lenguaje natural")
    model: Optional[str] = Field(default=MODELO_PRINCIPAL, description="Alias del modelo a usar (ej: 'gpt-4', 'llama-3')")

class QueryResponse(BaseModel):
    user_id: int
    question: str
    sql: str
    data: List[Dict[str, Any]] # Resultado de la query
    columns: List[str]         # Nombres de las columnas para el Frontend
    row_count: int
    execution_time: float      # Tiempo que tardó en segundos
    viz_type: VizType = Field(default="table")
    viz_title: Optional[str] = None

# --- 2. FUNCIONES AUXILIARES (DRY & Security) ---

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

# --- 3. ENDPOINT ---

@router.post("/ask", response_model=QueryResponse)
async def ask_database(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Motor de Inteligencia de Datos:
    1. Recibe pregunta + Modelo.
    2. Genera Plan Semántico (Router).
    3. Compila a SQL Seguro (Compiler).
    4. Ejecuta en Neon PostgreSQL.
    5. Guarda auditoría en segundo plano.
    6. Devuelve resultados JSON.
    """
    start_time = time.time()

    # --- INICIALIZACIÓN SEGURA (State Tracking) ---
    # Variables iniciales (para tener algo que loguear si falla al principio)
    generated_sql = ""
    query_plan_dict = {}
    row_count = 0
    viz_type_to_log = None
    viz_title_response = None
    sql_candidate = ""
    params_candidate = {}
    
    print(f"👤 [User {request.user_id}] Pregunta: '{request.question}' | Modelo: {request.model}")

    # =========================================================================
    # INTENTO 1: MOTOR DE REGLAS (Fast Path & Safe Execution) ⚡
    # =========================================================================
    try:
        rule_hit = check_rules(request.question)
        
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

            query_plan_dict = {
                "source": "rules_engine", 
                "match": "regex",
                "params": str(params_candidate)
            }
            
            _log_audit(background_tasks, request, sql_candidate, query_plan_dict, row_count, elapsed, viz_type_candidate)
            
            # RETORNO ANTICIPADO: Si esto funciona, NO ejecuta el LLM.
            return QueryResponse(
                user_id=request.user_id,
                question=request.question,
                sql=sql_candidate,
                data=df.to_dict(orient="records"),
                columns=list(df.columns),
                row_count=row_count,
                execution_time=elapsed,
                viz_type=viz_type_candidate,
                viz_title=viz_title_candidate
            )

    except Exception as e:
        # Si es ERROR DE SEGURIDAD (400), GUARDAMOS LOG Y PARAMOS TODO
        if isinstance(e, HTTPException) and e.status_code == 400:
            print(f"   ⛔ [SECURITY BLOCK] Ataque bloqueado.")
            # Logueamos el intento de ataque antes de morir
            elapsed = round(time.time() - start_time, 4)

            # Usamos .get() para evitar error si params_candidate no se llenó
            safe_params = str(params_candidate) if params_candidate else "Unknown"
            # Guardado SINCRONO (Directo, no background) para asegurar que se escriba
            save_audit_log(
                user_id=request.user_id, 
                question=request.question, 
                model="rules_engine", 
                query_plan={"error": "security_block", "params": safe_params}, 
                sql=sql_candidate, # Ahora sí guardamos el SQL que intentaron usar
                time_taken=elapsed, 
                rows=0, 
                error=str(e.detail), 
                viz_type="security_alert"
            )
            raise e # Relanzamos para que FastAPI devuelva 400 al usuario
        
        # Si es otro error, seguimos al LLM
        print(f"   ⚠️ [RULES ERROR] Fallback a LLM. Error: {e}")

    # =========================================================================
    # INTENTO 2: LLM (Fallback / Slow Path) 🤖
    # =========================================================================
    try:
        print(f"   🤖 [LLM START] Generando plan con Inteligencia Artificial...")

        # PASO A: Generar el Plan
        # -------------------------------------------------
        query_plan = generate_query_plan(request.question, llm_model_name=request.model)
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

        # PASO D: Auditoría EXITO (En segundo plano)
        _log_audit(background_tasks, request, generated_sql, query_plan_dict, row_count, elapsed, viz_type_to_log)
            
        # PASO E: Respuesta al Cliente
        return QueryResponse(
            user_id=request.user_id,
            question=request.question,
            sql=generated_sql,
            data=df.to_dict(orient="records"), # Convierte DataFrame a lista de objetos JSON
            columns=list(df.columns),
            row_count=len(df),
            execution_time=elapsed,
            viz_type=viz_type_to_log if viz_type_to_log else "table", # Fallback
            viz_title=viz_title_response
        )

    except Exception as e:
        # Cálculo del tiempo hasta el fallo
        elapsed = round(time.time() - start_time, 4)
        error_msg = str(e)

        # Logueamos el error real en consola del servidor
        print(f"❌ ERROR CRÍTICO [User {request.user_id}]: {error_msg}")

        # PASO F: Auditoría ERROR (En segundo plano)
        # Guardamos qué intentó preguntar y por qué falló
        try:
            _log_audit(background_tasks, request, generated_sql, query_plan_dict, 0, elapsed, viz_type_to_log or "error", str(e))
        except:
            print("   ❌ Falló el log de error crítico.")
        

        # Si fue un error de seguridad (400), lo respetamos. Si no, 500.
        # En producción, podrías ocultar el detalle 'str(e)' si fuera información sensible
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500, 
            detail=str(e)
            )