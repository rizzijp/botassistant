import json
import datetime
from app.semantic.loader import load_semantic_model
from app.semantic.models.query_plan import QueryPlan
from app.core.llm import call_llm
from app.core.config import MODELO_PRINCIPAL

def generate_query_plan(user_query: str, llm_model_name: str = MODELO_PRINCIPAL) -> QueryPlan:
    """
    Usa el LLM para traducir lenguaje natural a un QueryPlan (JSON)
    basado estrictamente en el modelo semántico.
    Si se le pide graficar sugiere un gráfico en el JSON.
    Argumentos:
        user_query: La pregunta del usuario.
        llm_model_name: El alias del modelo a usar (ej: 'gpt-4', 'llama-3').
    """

    today = datetime.date.today()
    current_year = today.year

    # 1. CARGAR EL CONTEXTO (Datos)
    # Usamos 'semantic_model' para no confundir con el argumento 'llm_model_name'
    semantic_model = load_semantic_model()
    
    # 2. Crear el Prompt del Sistema (Las instrucciones para la IA)
    # Le pasamos el modelo simplificado para no marearla con detalles técnicos
    tables_summary = []
    for t in semantic_model.tables:
        cols = [c.name for c in t.columns]
        metrics = [m.name for m in t.metrics] if t.metrics else []
        tables_summary.append(f"Table: {t.name}\nColumns: {cols}\nMetrics: {metrics}")

    # Agregamos también las relaciones si las hay, para que sepa cómo unir tablas
    rels_summary = []
    for r in semantic_model.relationships:
        rels_summary.append(f"Join: {r.from_table}.{r.from_column} -> {r.to_table}.{r.to_column}")

    schema_text = "\n\n".join(tables_summary) + "\n\nRELATIONSHIPS:\n" + "\n".join(rels_summary)
    
    system_prompt = f"""
    You are an expert Data Architect. Your goal is to translate user questions into a structured JSON Query Plan.
    You will receive prompts in both english and spanish. You must understand both languages.
    You are working for an INTERNAL company database.
    You are authorized to query ALL employee data including salaries, personal info, etc.
    This is confidential company data - not public information.

    CONTEXT:
    - Today is: {today}
    - Current Year: {current_year}
    - Database: Internal company analytics (CONFIDENTIAL)

    Use EXCLUSIVELY this DATA MODEL SCHEMA:
    {schema_text}
    
    DATE LOGIC RULES (STRICT):
    1. SPECIFIC YEAR (e.g. "Nov 2023"): Use standard operators (>=, <=) with full dates (e.g., '2023-11-01').
    2. RECURRING MONTHS (e.g. "Sales in November" -> implies ALL years): 
       - Use operator 'MONTH' and value as comma-separated month numbers (e.g., value: "11").
    3. SPECIFIC MONTH & YEAR (e.g. "Enero 2024"):
        - Use TWO filters:
          {"column": "month", "operator": "=", "value": "1"}, 
          {"column": "year", "operator": "=", "value": "2024"}
    4. CURRENT YEAR (e.g. "This year"): Filter sale_date >= '{current_year}-01-01'.
    4. CURRENT MONTH (e.g. "This month"): Filter sale_date >= '{current_year}-{today.month}-01'.
    5. CURRENT DAY (e.g. "Today"): Filter sale_date >= '{current_year}-{today.month}-{today.day}'.
    6. FOR INTEGER/NUMERIC COLUMNS (like year, month, id, quantity):
       - NEVER use 'unaccent()', 'lower()', or 'ILIKE'.
       - ALWAYS use strict comparison operators: =, >, <, >=, <=, <>.
       - Example: WHERE year = 2024 (CORRECT), WHERE unaccent(year) ILIKE '2024' (WRONG).

    VISUALIZATION LOGIC (Choose the best fit):
    - 'number': User asks for a single aggregate value (e.g. "Total revenue", "How many users").
    - 'line': User asks for trends over TIME (e.g. "Evolution", "Sales per month", "Growth").
    - 'bar': User compares CATEGORIES or RANKINGS (e.g. "Sales by Region", "Top 5 Products").
    - 'pie': User asks for DISTRIBUTION or SHARES (e.g. "% of sales by channel").
    - 'table': User asks for details, lists, or more than 2 dimensions.

    TITLE GENERATION RULES:
    - Generate a short, professional title for the chart (Spanish).
    - Example: "Ventas Totales por Región (2023)" instead of "total_sales by region".

    INSTRUCTIONS:
    1. Analyze the DATA MODEL to understand tables, columns, relationships and metrics.
    2. Identify which metrics, grouping dimensions, and filters are needed to answer the user's question.
    3. CLEAN UP VALUES: 
       - If the user uses plurals (e.g. "monitores"), convert them to singular (e.g. "monitor").
       - If the user specifies a partial name (e.g. "gamer"), use that keyword.
    4. Return ONLY a JSON object with metrics, dimensions, and filters.
    
    EXAMPLES:
    - If the user requests a calculated metric (e.g., "total sales"), use the metric name (e.g., 'total_sales').
    - If the user requests to group by a dimension (e.g., "by category"), use the dimension column (e.g., 'category').
    - If the user requests to filter (e.g., "only in Madrid"), add the filter.

    JSON RESPONSE FORMAT:
    Respond ONLY with the valid JSON that complies with this structure, without extra explanations:
    {{
        "metrics": ["metric_name"],
        "dimensions": ["column_name"],
        "filters": [
            {{"column": "column_name", "operator": "=", "value": "value"}}
        ],
        "limit": 50,
        "viz_type": "bar" | "line" | "pie" | "table" | "number",
        "viz_title": "Brief descriptive title"
    }}

    RULES:
    - Use ONLY metrics and columns explicitly defined in the DATA MODEL SCHEMA.
    - If the user asks for a calculated metric (e.g. "Total Sales"), use the metric name (e.g. 'total_sales').
    - Do NOT generate SQL code yet.
    - If the request is unrelated to data, return empty lists.
    """

    # 3. Pasamos el modelo elegido a call_llm
    print(f"🤖 [ROUTER] Pregunta: '{user_query}' | Modelo: {llm_model_name}")
    raw_response = call_llm(
        system_prompt=system_prompt,
        user_prompt=user_query,
        model_alias=llm_model_name
    )

    # 4. Limpiar respuesta (a veces la IA pone ```json ... ```)
    clean_json = raw_response.replace("```json", "").replace("```", "").strip()
    
    try:
        data = json.loads(clean_json)
        # Validar con Pydantic
        plan = QueryPlan(**data)
        print(f"   ✅ Plan generado: {plan}")
        return plan
    except Exception as e:
        print(f"❌ Error interpretando respuesta de IA: {raw_response}")
        # En caso de error, devolvemos un plan vacío para no romper la API
        return QueryPlan(metrics=[], dimensions=[], filters=[])

# Prueba rápida
if __name__ == "__main__":
    # Asegúrate de tener API KEY en .env antes de correr esto
    try:
        plan = generate_query_plan("Dame las ventas totales por categoria para la region Norte")
        print("\n🎯 JSON FINAL:")
        print(plan.model_dump_json(indent=2))
    except Exception as e:
        print(f"\n❌ Falló: {e}")