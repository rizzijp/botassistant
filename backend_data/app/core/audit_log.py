import json
from sqlalchemy import text
from app.db.connection import engine
# Importamos el tipo QueryPlan para type hinting
from app.semantic.models.query_plan import QueryPlan

def save_audit_log(
    user_id: int,
    question: str, 
    model: str, 
    query_plan: dict,
    sql: str, 
    time_taken: float, 
    rows: int, 
    error: str = None,
    viz_type: str = "table"):
    """
    Guarda un evento en la tabla 'audit.logs'.
    Esta función se debe ejecutar en BackgroundTasks para no frenar al usuario.
    """
    try:
        # Determinamos el status automáticamente
        status = "ERROR" if error else "SUCCESS"

        # Convertimos el plan a string JSON válido para Postgres
        # Si el plan vino vacío (fallo router), guardamos "{}"
        plan_json = json.dumps(query_plan) if query_plan else "{}"

        # SQL Parametrizado usando el esquema 'audit'
        # OJO: Los :nombres deben coincidir con las claves del diccionario de abajo
        stmt = text("""
            INSERT INTO audit.logs 
            (user_id, question, model_used, query_plan, sql_generated, status, execution_time_sec, row_count, error_message, viz_type)
            VALUES (:uid, :q, :mdl, :plan, :sql, :st, :time, :rows, :err, :viz)
        """)
        
        # Ejecutamos la inserción con commit automático
        with engine.begin() as conn:
            conn.execute(stmt, {
                "uid": user_id,
                "q": question,
                "mdl": model,
                "plan": plan_json,
                "sql": sql,
                "st": status,
                "time": time_taken,
                "rows": rows,
                "err": error,
                "viz": viz_type
            })

            # Print discreto para confirmar en consola
            icon = "✅" if status == "SUCCESS" else "❌"
            print(f"{icon} [AUDIT] Log guardado (User {user_id})")
            
    except Exception as e:
        # Si falla el log, NO rompemos la app, solo avisamos al admin (consola)
        print(f"⚠️ FATAL: No se pudo guardar el log de auditoría: {e}")