# GET /audit/logs (opcional para demo)
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.db.connection import engine
from typing import List, Dict, Any

router = APIRouter()

@router.get("/logs", response_model=List[Dict[str, Any]])
def get_recent_logs(limit: int = 10):
    """
    Recupera los últimos logs de auditoría para mostrar en la demo/dashboard.
    """
    try:
        query = text("""
            SELECT 
                log_id, timestamp, user_id, session_id,
                exito, mensaje, model_used, 
                sql_generado, execution_time_sec, total_filas, 
                error_message, tipo_grafica, tiene_grafica
            FROM audit.logs
            ORDER BY timestamp DESC
            LIMIT :limit
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {"limit": limit})
            # Convertimos filas SQL a lista de diccionarios
            logs = [dict(row._mapping) for row in result]
            
        return logs
        
    except Exception as e:
        print(f"❌ Error leyendo logs: {e}")
        raise HTTPException(status_code=500, detail=f"Error leyendo logs: {e}")