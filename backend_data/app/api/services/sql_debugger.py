import logging
from app.core.llm import call_llm

logger = logging.getLogger(__name__)

def fix_sql_with_llm(bad_sql: str, error_msg: str, model: str) -> str:
    """
    Agente especialista en reparación de SQL.
    Actúa como un 'Self-Healing Agent': recibe el error de la DB y reescribe la query.
    """
    logger.warning(f"   ⚠️ [SQL DEBUGGER] Iniciando reparación. Error detectado: {error_msg}")
    
    system_prompt = """
    You are an expert SQL Debugger Agent for PostgreSQL.
    Your ONLY goal is to fix the SQL query based on the error message provided.
    
    CRITICAL RULES:
    1. Output ONLY the raw SQL code. No markdown (```sql), no comments, no explanations.
    2. Do NOT change the business logic, only fix the syntax or column names.
    3. If the error is 'column does not exist', replace it with the closest valid column name.
    """
    
    user_prompt = f"""
    FAILING SQL:
    {bad_sql}
    
    POSTGRES ERROR:
    {error_msg}
    
    CORRECTED SQL:
    """
    
    try:
        # Llamamos al LLM (Llama-3) para que actúe como médico
        fixed_sql = call_llm(system_prompt, user_prompt, model_alias=model)
        
        # Limpieza quirúrgica: quitamos markdown si el LLM lo puso
        clean_sql = fixed_sql.replace("```sql", "").replace("```", "").strip()
        
        return clean_sql
        
    except Exception as e:
        logger.error(f"❌ [SQL DEBUGGER] El agente falló al intentar reparar: {e}")
        # Si el médico falla, devolvemos la query original para que el sistema lance el error real
        return bad_sql