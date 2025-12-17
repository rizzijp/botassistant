import logging
from app.core.llm import call_llm
from app.semantic.loader import load_semantic_model

logger = logging.getLogger(__name__)

def fix_sql_with_llm(bad_sql: str, error_msg: str, model: str) -> str:
    """
    Agente especialista en reparación de SQL con contexto del schema.
    Actúa como un 'Self-Healing Agent': recibe el error de la DB y reescribe la query.
    """
    logger.warning(f"   ⚠️ [SQL DEBUGGER] Iniciando reparación. Error detectado: {error_msg}")
    
    # Load schema to give LLM context
    semantic_model = load_semantic_model()
    
    # Build schema summary
    schema_info = []
    for table in semantic_model.tables:
        cols = [c.name for c in table.columns]
        schema_info.append(f"Table: {table.schema_name}.{table.name}\nColumns: {', '.join(cols)}")
    
    schema_text = "\n\n".join(schema_info)
    
    system_prompt = f"""
    You are an expert SQL Debugger Agent for PostgreSQL.
    
    AVAILABLE SCHEMA:
    {schema_text}
    
    CRITICAL RULES:
    1. Output ONLY the raw SQL code. No markdown (```sql), no comments, no explanations.
    2. Fix syntax/column errors using ONLY the columns listed above.
    3. If a column doesn't exist, use the closest valid column from the schema.
    4. Preserve business logic and WHERE clauses.
    5. Do NOT change table names or remove JOINs unless they're causing the error.
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
        
        logger.info(f"   ✅ [SQL DEBUGGER] SQL reparado exitosamente")
        return clean_sql
        
    except Exception as e:
        logger.error(f"❌ [SQL DEBUGGER] El agente falló al intentar reparar: {e}")
        # Si el médico falla, devolvemos la query original para que el sistema lance el error real
        return bad_sql