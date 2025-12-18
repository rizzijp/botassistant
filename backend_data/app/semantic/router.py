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
    - DATA BOUNDARIES: The database contains REAL historical data up to {today}. NO FUTURE DATA EXISTS. Do not generate filters for future dates.

    Use EXCLUSIVELY this DATA MODEL SCHEMA:
    {schema_text}

    # --- LOGIC RULES (HIERARCHY) ---
    
    1. DATE LOGIC RULES (Use virtual columns 'year'/'month' whenever possible):
        A. WHOLE YEAR (e.g. "Sales in 2023"):
            - Column: "year"
            - Operator: "="
            - Value: "2023"
            - (Compiler translates this to: EXTRACT(YEAR...) = 2023)
            
        B. SPECIFIC MONTH & YEAR (e.g. "Nov 2023"):
            - You must generate TWO filters:
                a) Column: "year", Operator: "=", Value: "2023"
                b) Column: "month", Operator: "=", Value: "11"
            
        C. RECURRING MONTHS (e.g. "Sales in November", "Every January", "Sales in November and December") -> implies ALL years): 
            - Column: "month".
            - Operator: "IN" (if multiple) or "=" (if single).
            - Value: Example: "11" (for =) or "11, 12" (for IN). Comma separated values for multiple months.
            - Example: "Nov and Dec" -> "month": "11, 12" (No year filter)
            
        D. CURRENT YEAR (e.g. "This year"): Filter sale_date >= '{current_year}-01-01'.

        E. CURRENT MONTH (e.g. "This month"): Filter sale_date >= '{current_year}-{today.month}-01'.

        F. CURRENT DAY (e.g. "Today"): Filter sale_date >= '{current_year}-{today.month}-{today.day}'.

        G. SPECIFIC DAY (e.g. "Yesterday", "Today", "On Dec 15th"):
           - CRITICAL: Do NOT use ranges (>=, <=).
           - ACTION: Use the casting function 'DATE(sale_timestamp)' in the column field.
           - Operator: "="
           - Value: 'YYYY-MM-DD' (The specific date).
           - Example: "Yesterday" -> Column: "DATE(sale_timestamp)", Operator: "=", Value: "2025-12-17"
           - (This ensures we capture the FULL day from 00:00 to 23:59).

        H. CUSTOM DATE RANGES (e.g. "First week of Jan", "From Jan 5th to Jan 10th", "Last 7 days"):
        - ONLY in this specific case use "sale_timestamp" with >= and <=.
        - YOU MUST ALWAYS GENERATE BOTH START AND END FILTERS.

    2. COMPARISON LOGIC (VS / OR) - CRITICAL:
       - IF the user explicitly mentions specific items to compare (e.g. "Nike vs Adidas", "Zapatillas vs Laptops"):
         A. MANDATORY FILTER: You MUST generate a filter.
         B. OPERATOR: Use "ILIKE_ANY".
         C. COLUMN SELECTION: Prefer "product_name". Use "category" ONLY if the term is clearly a high-level group.
         D. CLEANUP: Singularize terms (Laptops -> Laptop).
         E. VALUE: Comma-separated keywords.
         
         F. DIMENSION STRATEGY (CRITICAL):
            - IF the user does NOT specify a grouping (e.g. does not say "by region"):
              You MUST group by the SAME column used in the filter.
              Reason: To show the breakdown of the specific items requested.
            - IF the user specifies a grouping (e.g. "by category"):
              Respect the user's requested dimension.

         G. EXAMPLE:
            User: "Zapatillas vs Laptops" (No grouping specified)
            Result: 
              Filters -> [{{ "column": "product_name", "operator": "ILIKE_ANY", "value": "Zapatilla,Laptop" }}]
              Dimensions -> ["product_name"]  <-- Matches the filter column

    3. DIMENSION TRANSFORMATION RULES (GROUPING) - CRITICAL:
       A. TIME DIMENSIONS (MANDATORY):
          - NEVER, EVER group by raw 'sale_timestamp'. It contains precise time (HH:MM:SS) and will break the chart.
          - FOR DAILY GROUPING: You MUST use the transformation "DATE(sale_timestamp)".
          - FOR MONTHLY GROUPING: You MUST use "TO_CHAR(sale_timestamp, 'YYYY-MM')".
          - FOR YEARLY GROUPING: You MUST use "EXTRACT(YEAR FROM sale_timestamp)".
       
       B. EXAMPLES:
          - User: "Ventas por día" -> Dimension: ["DATE(sale_timestamp)"]
          - User: "Tendencia diaria" -> Dimension: ["DATE(sale_timestamp)"]
          - User: "Ventas por mes" -> Dimension: ["TO_CHAR(sale_timestamp, 'YYYY-MM')"]
          - User: "Tendencia mensual" -> Dimension: ["TO_CHAR(sale_timestamp, 'YYYY-MM')"]
          - User: "Ventas por año" -> Dimension: ["EXTRACT(YEAR FROM sale_timestamp)"]
          - User: "Tendencia anual" -> Dimension: ["EXTRACT(YEAR FROM sale_timestamp)"]

    4. METRIC SELECTION RULES:
       A. "Average Daily Sales" / "Promedio de ventas por día":
          - CONTEXT: Usually implies seeing the daily trend of REVENUE.
          - ACTION: Metric: "total_sales" (SUM), Dimension: "DATE(sale_timestamp)".
          - NOTE: Do NOT use AVG(total) (that is Average Ticket).
       
       B. "Average Ticket" / "Ticket Promedio":
          - ACTION: Metric: "avg_ticket" (AVG).
       
       C. "Quantity" / "Unidades":
          - ACTION: Metric: "total_quantity".
    

    5. INTEGER/NUMERIC COLUMNS (like year, month, id, quantity):
            - ALWAYS use strict comparison operators: =, >, <, >=, <=, <>, IN.
            - NEVER use 'unaccent()', 'lower()', or 'ILIKE'.
            - Example: WHERE year = 2024 (CORRECT), WHERE unaccent(year) ILIKE '2024' (WRONG).

    6. STRING COLUMNS: Clean up values (singularize).
       - If the user uses PLURALS (e.g. "monitores"), convert them to SINGULAR (e.g. "monitor") for ILIKE searches.
       - If the user specifies a partial name (e.g. "gamer"), use that keyword.

    7. DETAILED RECORDS / RAW DATA (CRITICAL):
       - TRIGGER: If the user asks for "details", "list", "raw data", "transactions", "all columns" (e.g. "Dame el detalle", "Ver ventas de ayer").
       - ACTION: Do NOT calculate SUM() or AVG(). You want a raw table.
       - METRICS: [] (Leave empty).
       - DIMENSIONS: Select the readable columns to describe the transaction.
         * MANDATORY: Include 'sale_id' (to ensure unique rows).
         * RECOMMENDED: 'sale_timestamp', 'product_name' (via join), 'quantity', 'total', 'customer_id' (if requested).
       - VIZ TYPE: "table".

    # --- OUTPUT FORMAT ---

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
    3. KEYWORD CLEANING (CRITICAL): 
       - FOR SEARCH FILTERS (ILIKE/ILIKE_ANY): ALWAYS convert search terms to their SINGULAR or ROOT form.
       - "Laptops" -> "Laptop" (Matches "HP Laptop" and "Laptops")
       - "Monitores" -> "Monitor"
       - "Celulares" -> "Celular"
       - "Zapatillas" -> "Zapatilla"
       - "Running shoes" -> "Running" (Broader is better for SQL matching)
    4. Return ONLY a JSON object with metrics, dimensions, and filters.

    EXAMPLES:
    - If the user requests a calculated metric (e.g., "total sales"), use the metric name (e.g., 'total_sales').
    - If the user requests to group by a dimension (e.g., "by category"), use the dimension column (e.g., 'category').
    - If the user requests to filter (e.g., "only in Argentina"), add the filter.

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

    CRITICAL OUTPUT RULES:
    - NO explanations. NO thinking process. NO introduction.
    - NO markdown formatting (do not use ```json).
    - If you talk or explain, the system crashes.

    RULES:
    - Use ONLY metrics and columns explicitly defined in the DATA MODEL SCHEMA.
    - If the user asks for a calculated metric (e.g. "Total Sales"), use the metric name (e.g. 'total_sales').
    - Do NOT generate SQL code yet.
    - If the request is unrelated to data, return empty lists.
    - TIME GROUPING: When grouping by time, ALWAYS use date truncation (e.g. 'DATE(sale_timestamp)'). NEVER group by raw timestamp.
    - DAILY AVERAGE: For 'daily average sales', first calculate the total per day, or show the daily trend. Do NOT use AVG(total) blindly.

   
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