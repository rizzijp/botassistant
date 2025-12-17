from app.semantic.models.query_plan import QueryPlan
from app.semantic.loader import load_semantic_model
import re

def compile_sql(plan: QueryPlan) -> str:
    """
    Traduce un QueryPlan (JSON) a SQL ejecutable de PostgreSQL.
    Versión corregida (v2):
    - Fuerza JOINs si hay métricas de hechos (arregla 'column does not exist').
    - Traduce YEAR()/MONTH() a EXTRACT (arregla 'function does not exist').
    - Detecta subconsultas en filtros y NO les pone comillas (arregla syntax error).
    """
    model = load_semantic_model()

    # 1. Identificar tablas necesarias basadas en Dimensiones y Filtros
    all_columns = set(plan.dimensions) | {f.column for f in plan.filters}
    needed_tables = set()
    
    # Mapeo previo para saber qué tablas necesitamos
    for table in model.tables:
        for col in table.columns:
            if col.name in all_columns:
                needed_tables.add(table.name)

    # 2. Lógica de Optimización vs JOINS
    # Si hay métricas (ej: total_sales), CASI SIEMPRE necesitamos la tabla de hechos (sales).
    # La optimización de "tabla única" solo vale si NO pedimos métricas de hechos.
    metric_needs_fact = False
    if plan.metrics:
        fact_table_def = next(t for t in model.tables if t.name == 'sales')
        fact_metrics = [m.name for m in fact_table_def.metrics] if fact_table_def.metrics else []
        fact_cols = [c.name for c in fact_table_def.columns]
        
        # Si pedimos una métrica calculada O una columna cruda de 'sales' (como 'total')
        if any(m in fact_metrics for m in plan.metrics) or \
           any(m in fact_cols for m in plan.metrics):
            metric_needs_fact = True

    # DECISIÓN: ¿Consultamos tabla simple o hacemos JOINS?
    use_simple_query = (len(needed_tables) == 1) and \
                       ('sales' not in needed_tables) and \
                       (not metric_needs_fact)

    # --- CAMINO A: CONSULTA SIMPLE (Solo Dimensiones) ---
    if use_simple_query:
        primary_table = next(t for t in model.tables if t.name in needed_tables)
        
        select_clauses = []
        for dim in plan.dimensions:
            select_clauses.append(f"{primary_table.name}.{dim}")
        
        # Rara vez habrá métricas aquí, pero por si acaso
        for metric in plan.metrics:
            select_clauses.append(metric)
        
        where_clauses = _build_where_clauses(plan.filters, primary_table.name)
        
        sql = f"SELECT {', '.join(select_clauses)}\nFROM {primary_table.schema_name}.{primary_table.name}"
        if where_clauses:
            sql += f"\nWHERE {' AND '.join(where_clauses)}"
        if plan.dimensions:
            sql += f"\nORDER BY {plan.dimensions[0]} DESC"
        if plan.limit:
            sql += f"\nLIMIT {plan.limit}"
        
        return sql

    else:
        # --- CAMINO B: MODO COMPLEJO (JOINS con Fact Table) ---
        fact_table = next(t for t in model.tables if t.name == 'sales')
        fact_columns = [c.name for c in fact_table.columns]

        # Recolectamos columnas necesarias (dims + filters)
        needed_columns = set(plan.dimensions)
        for f in plan.filters:
            needed_columns.add(f.column)

        col_map = {} 
        joins = []
        processed_tables = set()

        # 3. Construcción de JOINS y Mapeo de Columnas
        for raw_col in needed_columns:
            # Limpieza: Extraer nombre base si viene como YEAR(col)
            simple_col_name = raw_col
            if "(" in raw_col:
                match = re.search(r'\((.*?)\)', raw_col)
                if match:
                    simple_col_name = match.group(1)

            # Quitar prefijos si existen
            col_name = simple_col_name.split(".")[-1]

            # Buscar a qué tabla pertenece
            if col_name in fact_columns:
                col_map[raw_col] = f"{fact_table.name}.{col_name}"
            else:
                dim_table = None
                for t in model.tables:
                    if any(c.name == col_name for c in t.columns):
                        dim_table = t
                        break
                
                if dim_table:
                    # Mapeamos usando el nombre original (raw) para encontrarlo luego
                    col_map[simple_col_name] = f"{dim_table.name}.{col_name}"
                    # Si era una funcion, intentamos mapear también la clave compleja
                    if simple_col_name != raw_col:
                         col_map[raw_col] = f"{dim_table.name}.{col_name}"

                    # Generar JOIN
                    if dim_table.name not in processed_tables and dim_table.name != fact_table.name:
                        rel = next((r for r in model.relationships 
                                    if r.from_table == fact_table.name and r.to_table == dim_table.name), None)
                        if rel:
                            joins.append(f"JOIN {dim_table.schema_name}.{dim_table.name} ON {fact_table.name}.{rel.from_column} = {dim_table.name}.{rel.to_column}")
                            processed_tables.add(dim_table.name)

        # 4. Construir SELECT (Traduciendo funciones)
        select_clauses = []
        
        for dim in plan.dimensions:
            # Detectar funciones de fecha no válidas en Postgres
            if "YEAR(" in dim.upper():
                inner = re.search(r'\((.*?)\)', dim).group(1)
                # Asumimos que si pide año es de la tabla de hechos o mapeada
                col_ref = col_map.get(inner, f"{fact_table.name}.{inner}")
                select_clauses.append(f"EXTRACT(YEAR FROM {col_ref})")
            
            elif "MONTH(" in dim.upper():
                inner = re.search(r'\((.*?)\)', dim).group(1)
                col_ref = col_map.get(inner, f"{fact_table.name}.{inner}")
                select_clauses.append(f"EXTRACT(MONTH FROM {col_ref})")
            
            else:
                # Columna normal
                select_clauses.append(col_map.get(dim, f"{fact_table.name}.{dim}"))

        # Métricas
        for metric_name in plan.metrics:
            metric_def = next((m for m in fact_table.metrics if m.name == metric_name), None)
            if metric_def:
                select_clauses.append(f"{metric_def.sql} AS {metric_name}")
            else:
                # Si piden 'total' o 'quantity' crudo
                if metric_name in fact_columns:
                    select_clauses.append(f"{fact_table.name}.{metric_name}")
                else:
                    select_clauses.append(metric_name)

        # 5. Construir WHERE
        # Pre-procesamos los filtros para asignarles su tabla correcta usando col_map
        mapped_filters = []
        for f in plan.filters:
            # Intentamos resolver el nombre cualificado
            if f.column in col_map:
                f.column = col_map[f.column]
            elif f.column in fact_columns:
                f.column = f"{fact_table.name}.{f.column}"
            # Si no, lo dejamos pasar (probablemente falle, pero ya hicimos lo posible)
            mapped_filters.append(f)

        where_clauses = _build_where_clauses(mapped_filters, default_table=fact_table.name)

        # 6. Ensamblar Query
        sql = f"SELECT {', '.join(select_clauses)} \nFROM {fact_table.schema_name}.{fact_table.name}"
        if joins:
            sql += "\n" + "\n".join(joins)
        if where_clauses:
            sql += "\nWHERE " + " AND ".join(where_clauses)
            
        if plan.dimensions:
            # Group by índices posicionales para evitar errores con alias/funciones
            indices = [str(i+1) for i in range(len(plan.dimensions))]
            sql += f"\nGROUP BY {', '.join(indices)}"

        if plan.metrics:
            sql += f"\nORDER BY {plan.metrics[0]} DESC"
            
        if plan.limit:
            sql += f"\nLIMIT {plan.limit}"
            
        return sql

def _build_where_clauses(filters, default_table):
    clauses = []
    # Nombre de columna de fecha por defecto
    REAL_DATE_COL = f"{default_table}.sale_timestamp"

    for f in filters:
        col = f.column
        op = f.operator.strip("',\" ")
        val = f.value

        # --- Traducción de Fechas ---
        if f.column == 'year' or f.column.endswith('.year'): # .year es raro pero posible
            clauses.append(f"EXTRACT(YEAR FROM {REAL_DATE_COL}) {op} {val}")
        elif f.column == 'month' or f.column.endswith('.month'):
            clauses.append(f"EXTRACT(MONTH FROM {REAL_DATE_COL}) {op} {val}")
        elif op == "MONTH":
            clauses.append(f"EXTRACT(MONTH FROM {REAL_DATE_COL}) IN ({val})")
        
        else:
            # --- Manejo de Valores (Strings vs Subqueries) ---
            final_val = val
            
            if isinstance(val, str):
                # Si parece una subconsulta (empieza con parentesis y SELECT)
                val_clean = val.strip()
                is_subquery = val_clean.startswith("(") and "SELECT" in val_clean.upper()
                
                if (op.upper() in ["IN", "NOT IN"]) and (val_clean.startswith("(") or is_subquery):
                    # NO poner comillas
                    final_val = val_clean
                elif op in ["=", "LIKE", "ILIKE"]:
                    # Búsqueda de texto normal
                    clean_str = val.replace("%", "")
                    clauses.append(f"unaccent({col}) ILIKE unaccent('%%{clean_str}%%')")
                    continue 
                else:
                    # String normal
                    final_val = f"'{val}'"
            
            clauses.append(f"{col} {op} {final_val}")
            
    return clauses