from sqlalchemy import text
from app.db.connection import engine
import json

def save_audit_log(
    user_id: int,
    session_id: str,
    mensaje: str,
    model_used: str,
    sql_generado: str,
    execution_time_sec: float,
    total_filas: int,
    error_message: str,
    tipo_grafica: str,
    tiene_grafica: bool = False
    ):
    """
    Guarda un evento en la tabla 'audit.logs'.
    Esta función se debe ejecutar en BackgroundTasks para no frenar al usuario.
    """
    try:
        # Calculamos 'exito' aquí adentro basándonos en si hay error
        # (Asumo que si error_message tiene texto, exito es False)
        es_exito = False if error_message else True

        # SQL Parametrizado usando el esquema 'audit'
        # OJO: Los :nombres deben coincidir con las claves del diccionario de abajo
        stmt = text("""
            INSERT INTO audit.logs 
            (user_id, session_id, exito, mensaje, model_used, sql_generado, execution_time_sec, total_filas, error_message, tipo_grafica, tiene_grafica)
            VALUES (:uid, :sid, :ex, :msg, :mdl, :sql, :time, :rows, :err, :viz, :has_viz)
        """)
        
        # Ejecutamos la inserción con commit automático
        with engine.begin() as conn:
            conn.execute(stmt, {
                "uid": user_id,
                "sid": session_id,
                "msg": mensaje,
                "ex": es_exito,
                "mdl": model_used,
                "sql": sql_generado,
                "time": execution_time_sec,
                "rows": total_filas,
                "err": error_message,
                "viz": tipo_grafica,
                "has_viz": tiene_grafica,
            })

            print(f"✅ [AUDIT] Log guardado. Sesión: {session_id}")
            
    except Exception as e:
        # Si falla el log, NO rompemos la app, solo avisamos al admin (consola)
        print(f"⚠️ FATAL: No se pudo guardar el log de auditoría: {e}")