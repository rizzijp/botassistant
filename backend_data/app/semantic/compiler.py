from app.semantic.models.query_plan import QueryPlan

def _clean_col_ref(col: str, main_table: str = "sales") -> str:
    """
    Decide inteligentemente el prefijo de la tabla.
    """
    # 1. Passthrough si es función o ya tiene tabla
    if "(" in col or "." in col:
        return col
    
    # 2. Mapeo de Tablas Dimensión
    products_cols = ["product_id", "product_name", "category", "unit_price"]
    customers_cols = ["customer_id","first_name_customer", "last_name_customer", "email", "region"]
    employees_cols = ["employee_id", "first_name", "last_name", "email", "position", "department", "salary"]
    users_cols = ["user_id", "role", "email", "password"]
    
    if col in products_cols:
        return f"products.{col}"
    
    if col in customers_cols:
        return f"customers.{col}"

    if col in employees_cols:
        return f"employees.{col}"
    
    if col in users_cols:
        return f"users.{col}"

    # 3. Default a Sales
    return f"{main_table}.{col}"

def compile_sql(query_plan: QueryPlan) -> str:
    """
    Convierte el QueryPlan (JSON) en SQL ejecutable para PostgreSQL.
    """
    main_table = "sales"
    
    # 1. CONSTRUIR SELECT
    # ---------------------------------------------------------
    select_items = []
    
    dims_clean = []
    for dim in query_plan.dimensions:
        # Parche de seguridad: timestamp puro -> DATE()
        if dim.strip() == "sale_timestamp" or dim.strip() == "sales.sale_timestamp":
            dims_clean.append(f"DATE({main_table}.sale_timestamp)")
        else:
            dims_clean.append(_clean_col_ref(dim, main_table))
    
    select_items.extend(dims_clean)
    
    metrics_sql = []
    for metric in query_plan.metrics:
        if metric == "total_sales":
            metrics_sql.append("SUM(sales.total) AS total_sales")
        elif metric == "avg_ticket":
            metrics_sql.append("AVG(sales.total) AS avg_ticket")
        elif metric == "count_transactions":
            metrics_sql.append("COUNT(sales.sale_id) AS count_transactions")
        elif metric == "total_quantity":
            metrics_sql.append("SUM(sales.quantity) AS total_quantity")
        else:
            metrics_sql.append(_clean_col_ref(metric, main_table))
            
    select_items.extend(metrics_sql)

    if not select_items: select_items = ["*"]
    select_clause = f"SELECT {', '.join(select_items)}"

    # 2. CONSTRUIR FROM y JOINS
    # ---------------------------------------------------------
    from_clause = f"FROM public.{main_table}"
    
    # Joins ESTÁTICOS (Unimos todo para que cualquier filtro funcione)
    joins = []
    joins.append("JOIN public.products ON sales.product_id = products.product_id")
    joins.append("JOIN public.customers ON sales.customer_id = customers.customer_id")
    joins.append("JOIN public.employees ON sales.employee_id = employees.employee_id")
    
    join_clause = " ".join(joins)

    # 3. CONSTRUIR WHERE
    # ---------------------------------------------------------
    where_conditions = []
    for f in query_plan.filters:
        raw_col = f.column.lower()
        op = f.operator.upper()
        val = f.value

        # --- Traducción de Columnas Virtuales ---
        if raw_col == 'year':
            col = f"EXTRACT(YEAR FROM {main_table}.sale_timestamp)"
        elif raw_col == 'month':
            col = f"EXTRACT(MONTH FROM {main_table}.sale_timestamp)"
        elif raw_col == 'day':
             col = f"EXTRACT(DAY FROM {main_table}.sale_timestamp)"
        else:
            col = _clean_col_ref(f.column, main_table)

        # --- Lógica de Operadores ---
        if op == "=":
            where_conditions.append(f"{col} = '{val}'")
        elif op in [">", "<", ">=", "<=", "<>"]:
            where_conditions.append(f"{col} {op} '{val}'")
        elif op == "IN":
            where_conditions.append(f"{col} IN ({val})")
        elif op == "ILIKE":
            where_conditions.append(f"unaccent({col}) ILIKE unaccent('%%{val}%%')")
        elif op == "ILIKE_ANY":
            terms = [t.strip() for t in val.split(",")]
            or_parts = []
            for term in terms:
                clean_term = term.replace("%", "")
                if len(clean_term) > 3 and clean_term.endswith("s"):
                    clean_term = clean_term[:-1]
                or_parts.append(f"unaccent({col}) ILIKE unaccent('%%{clean_term}%%')")
            if or_parts:
                where_conditions.append(f"({' OR '.join(or_parts)})")

    where_clause = ""
    if where_conditions:
        where_clause = "WHERE " + " AND ".join(where_conditions)

    # 4. CONSTRUIR GROUP BY
    # ---------------------------------------------------------
    group_by_clause = ""
    if metrics_sql and dims_clean:
        indices = [str(i+1) for i in range(len(dims_clean))]
        group_by_clause = f"GROUP BY {', '.join(indices)}"

    # 5. CONSTRUIR ORDER BY (Lógica Temporal Inteligente)
    # ---------------------------------------------------------
    order_by_clause = ""
    
    time_dim_index = None
    for i, dim in enumerate(dims_clean):
        d_upper = dim.upper()
        if "DATE(" in d_upper or "TO_CHAR(" in d_upper or "EXTRACT(" in d_upper or "YEAR" in d_upper:
            time_dim_index = i + 1
            break
            
    if time_dim_index:
        order_by_clause = f"ORDER BY {time_dim_index} ASC"
    elif metrics_sql:
        first_metric_alias = metrics_sql[0].split(" AS ")[-1]
        order_by_clause = f"ORDER BY {first_metric_alias} DESC"
    elif dims_clean:
        order_by_clause = "ORDER BY 1 DESC"

    # 6. LIMIT
    limit_clause = f"LIMIT {query_plan.limit}"

    # 7. ENSAMBLAR
    final_sql = f"""
    {select_clause}
    {from_clause}
    {join_clause}
    {where_clause}
    {group_by_clause}
    {order_by_clause}
    {limit_clause}
    """
    
    return final_sql.strip()