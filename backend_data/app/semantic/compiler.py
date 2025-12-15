from app.semantic.semantic_types import QueryPlan
from app.semantic.loader import load_semantic_model

def compile_sql(plan: QueryPlan) -> str:
    """
    Traduce un QueryPlan (JSON) a SQL ejecutable de PostgreSQL.
    Genera JOINs tanto para dimensiones como para filtros.
    Características:
    - Dinámico: Lee relaciones y métricas desde semantic_model.yaml
    - Flexible: Usa unaccent e ILIKE para búsquedas de texto.
    Soporta fechas relativas y limpia operadores sucios.
    """
    # Cargamos el modelo para entender las relaciones y definiciones reales
    model = load_semantic_model()
    
    # 1. Identificar tabla de hechos
    fact_table = next(t for t in model.tables if t.name == 'fact_sales')
    fact_columns = [c.name for c in fact_table.columns]
    
    # 2. Recopilar todas las columnas necesarias (Dimensiones + Filtros)
    #    Para saber qué tablas necesitamos unir.
    needed_columns = set(plan.dimensions)
    for f in plan.filters:
        needed_columns.add(f.column)

    # Diccionario para saber a qué tabla pertenece cada columna
    # Clave: 'dim_product.category' (o 'category') -> Valor: 'dim_product'
    col_map = {}
        
    # 3. Construir JOINs
    #    Empezamos con la tabla de hechos
    from_clause = f"{fact_table.schema_name}.{fact_table.name}"
    joins = []
    processed_tables = set()

    for raw_col in needed_columns:
        # A. LIMPIEZA DE PREFIJOS
        # Si la columna viene como 'dim_product.category', nos quedamos solo con 'category'
        # para buscarla en el diccionario de tablas.
        col_name = raw_col.split(".")[-1] if "." in raw_col else raw_col

        # B. LÓGICA DE DETECCIÓN
        # ¿Está en la tabla de hechos?
        if col_name in fact_columns:
            # Mapeo directo: 'total' -> 'fact_sales.total'
            col_map[raw_col] = col_name

        else:
            # Si la columna no está en la tabla de hechos, buscamos en qué dimensión vive
            dim_table = None
            # Buscamos en qué tabla vive esta columna
            for t in model.tables:
                if any(c.name == col_name for c in t.columns):
                    dim_table = t
                    break
            
            # Si encontramos la tabla...
            if dim_table:
                # Mapeo dimensión: 'category' -> 'dim_product.category'
                col_map[raw_col] = f"{dim_table.name}.{col_name}"
                # ... y si no hemos hecho el JOIN...
                if dim_table.name not in processed_tables and dim_table.name != fact_table.name:
                    # Buscamos la relación en el modelo (Foreign Key)
                    rel = next((r for r in model.relationships 
                                if r.from_table == fact_table.name and r.to_table == dim_table.name), None)
                    
                    if rel:
                        # Generamos el JOIN SQL
                        join_sql = f"JOIN {dim_table.schema_name}.{dim_table.name} ON {fact_table.name}.{rel.from_column} = {dim_table.name}.{rel.to_column}"
                        joins.append(join_sql)
                        processed_tables.add(dim_table.name)

    # 4. Construir SELECT
    select_clauses = []
    # A. Dimensiones
    for dim in plan.dimensions:
        select_clauses.append(col_map.get(dim, dim))
    # B. Métricas (Buscamos la definición SQL real, ej: SUM(total))
    for metric_name in plan.metrics:
        metric_def = next((m for m in fact_table.metrics if m.name == metric_name), None)
        if metric_def:
            select_clauses.append(f"{metric_def.sql} AS {metric_name}")
        else:
            # Fallback por si la IA inventó un nombre, lo pasamos directo
            select_clauses.append(metric_name)

    # 5. Construir WHERE
    where_clauses = []

    # Define aquí el nombre REAL de tu columna de fecha en la DB de Render
    REAL_DATE_COL = "sales.sale_timestamp"
    
    for f in plan.filters:
        col = col_map.get(f.column, f.column)
        # LIMPIEZA DE OPERADOR: Quitamos comillas o comas extra que la IA alucine
        # Si la IA manda ">='" lo convertimos a ">="
        op = f.operator.strip("',\" ")
        val = f.value


        # --- LÓGICA VIRTUAL DE FECHAS ---
        # Si la IA pide filtrar por 'year', usamos la columna timestamp real
        if f.column == 'year':
            where_clauses.append(f"EXTRACT(YEAR FROM {REAL_DATE_COL}) {op} {val}")
            
        # Si la IA pide filtrar por 'month', extraemos el mes
        elif f.column == 'month':
            where_clauses.append(f"EXTRACT(MONTH FROM {REAL_DATE_COL}) {op} {val}")
            
        # Lógica para operador MONTH recurrente (ej: "ventas en noviembre")
        elif op == "MONTH":
            where_clauses.append(f"EXTRACT(MONTH FROM {REAL_DATE_COL}) IN ({val})")

        # --- RESTO DE LA LÓGICA (Texto y Números) ---
        elif isinstance(val, str) and op in ["=", "LIKE", "ILIKE"]:
             clean_val = val.replace("%", "")
             where_clauses.append(f"unaccent({col}) ILIKE unaccent('%%{clean_val}%%')")
        else:
            formatted_val = f"'{val}'" if isinstance(val, str) else val
            where_clauses.append(f"{col} {op} {formatted_val}")


    # 6. Ensamblar Query Final
    sql = f"SELECT {', '.join(select_clauses)} \nFROM {from_clause}"
    
    if joins:
        sql += "\n" + "\n".join(joins)
        
    if where_clauses:
        sql += "\nWHERE " + " AND ".join(where_clauses)
        
    if plan.dimensions:
        indices = [str(i+1) for i in range(len(plan.dimensions))]
        sql += f"\nGROUP BY {', '.join(indices)}"

    # Si hay métricas, ordenamos por la primera de mayor a menor (Top ventas, etc.)
    if plan.metrics:
        # Usamos el alias de la primera métrica
        sql += f"\nORDER BY {plan.metrics[0]} DESC"
        
    if plan.limit:
        sql += f"\nLIMIT {plan.limit}"
        
    return sql

# --- Prueba Rápida ---
if __name__ == "__main__":
    from app.semantic.semantic_types import Filter
    
    # Caso de prueba difícil: Agrupar por CATEGORÍA (Producto) pero filtrar por REGIÓN (Cliente)
    test_plan = QueryPlan(
        metrics=["total_sales"],
        dimensions=["category"], 
        filters=[Filter(column="region", operator="=", value="Norte")],
        limit=5
    )
    
    print("🏗️ Generando SQL de Prueba...")
    try:
        print(compile_sql(test_plan))
    except Exception as e:
        print(f"❌ Error: {e}")