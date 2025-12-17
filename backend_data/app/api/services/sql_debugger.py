from app.semantic.loader import load_semantic_model
def fix_sql_with_llm(bad_sql: str, error_msg: str, model: str) -> str:
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
    1. Output ONLY the raw SQL code. No markdown, no comments.
    2. Fix syntax/column errors using ONLY the columns listed above.
    3. If a column doesn't exist, use the closest valid column from the schema.
    4. Preserve business logic and WHERE clauses.
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