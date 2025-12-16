import re
import unicodedata
from typing import Optional, Dict, Any

def normalize_text(text: str) -> str:
    """
    Normaliza el texto eliminando tildes y convirtiendo a minúsculas
    para facilitar el matcheo de Regex.
    """
    text = text.lower().strip()
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', text)

# --- NOMBRES REALES DE LA BASE DE DATOS ---
TABLE_SALES = "public.sales"
TABLE_PROD  = "public.products"
TABLE_CUST  = "public.customers"
TABLE_EMP   = "public.employees"
COL_DATE    = "sale_timestamp"

# --- CATÁLOGO DE REGLAS ---
RULES_CATALOG = [
    # -------------------------------------------------------------------------
    # 1. SALUDOS
    # -------------------------------------------------------------------------
    {
        "patterns": [r"^hola$", r"^buenos dias$", r"^buenas tardes$", r"^que tal$"],
        "response_template": {
            "sql": "SELECT '¡Hola! Soy tu asistente de datos. Pregúntame sobre ventas, empleados, clientes o productos.' as mensaje",
            "viz_type": "number",
            "viz_title": "Saludo"
        }
    },

    # -------------------------------------------------------------------------
    # 2. RECURSOS HUMANOS (Empleados)
    # -------------------------------------------------------------------------
    # Ficha del empleado
    {
        "patterns": [
            r"^salario (?:de |del )?(.+)$",
            r"^cuanto gana (?:el empleado |la empleada )?(.+)$",
            r"^puesto (?:de |del )?(.+)$",
            r"^cargo (?:de |del )?(.+)$",
            r"^datos (?:del empleado )?(.+)$",
            r"^quien es (?:el empleado )?(.+)$"
        ],
        "response_template": {
            "sql": """
                SELECT 
                    employee_id,
                    CONCAT(first_name, ' ', last_name) as nombre_completo, 
                    position as cargo, 
                    department as departamento, 
                    email, 
                    salary as salario_mensual
                FROM {TABLE_EMP}
                WHERE unaccent(first_name) ILIKE unaccent(%(p1)s) 
                   OR unaccent(last_name) ILIKE unaccent(%(p1)s)
                   OR unaccent(CONCAT(first_name, ' ', last_name)) ILIKE unaccent(%(p1)s)
            """,
            "viz_type": "table",
            "viz_title": "Ficha de Empleado: {captured}"
        },
        "params_mapper": lambda captured: f"%{captured}%"
    },
    # Top Salarios
    {
        "patterns": [
            r"^top (\d+) (?:de )?salarios?$",
            r"^top (\d+) (?:de )?empleados (?:mejor |peor )?pagados?$",
            r"^los (\d+) (?:empleados )?con (?:mas|mayor) sueldo$"
        ],
        "response_template": {
            "sql": """
                SELECT 
                    CONCAT(first_name, ' ', last_name) as empleado, 
                    salary, 
                    department, 
                    position
                FROM {TABLE_EMP}
                ORDER BY salary DESC
                LIMIT %(p1)s
            """,
            "viz_type": "bar",
            "viz_title": "Top {captured} Salarios más Altos"
        },
        "params_mapper": lambda captured: int(captured)
    },

    # -------------------------------------------------------------------------
    # 3. CLIENTES
    # -------------------------------------------------------------------------
    {
        "patterns": [
            r"^cliente (.+)$",
            r"^datos (?:del |de )?cliente (.+)$",
            r"^buscar cliente (.+)$",
            r"^contacto (?:de |del )?(.+)$"
        ],
        "response_template": {
            "sql": """
                SELECT 
                    customer_id,
                    CONCAT(first_name_customer, ' ', last_name_customer) as cliente,
                    email,
                    region
                FROM {TABLE_CUST}
                WHERE unaccent(first_name_customer) ILIKE unaccent(%(p1)s) 
                   OR unaccent(last_name_customer) ILIKE unaccent(%(p1)s)
                   OR unaccent(CONCAT(first_name_customer, ' ', last_name_customer)) ILIKE unaccent(%(p1)s)
                LIMIT 10
            """,
            "viz_type": "table",
            "viz_title": "Información del Cliente: {captured}"
        },
        "params_mapper": lambda captured: f"%{captured}%"
    },

    # -------------------------------------------------------------------------
    # 4. CATÁLOGO Y PRECIOS
    # -------------------------------------------------------------------------
    {
        "patterns": [
            r"^precio (?:del? |de los )?(.+)$",
            r"^cuanto cuesta(?:n)? (?:el |los |las )?(.+)$",
            r"^valor (?:del? )?(.+)$"
        ],
        "response_template": {
            "sql": """
                SELECT product_name, category, unit_price
                FROM {TABLE_PROD}
                WHERE unaccent(product_name) ILIKE unaccent(%(p1)s)
                   OR unaccent(category) ILIKE unaccent(%(p1)s)
                ORDER BY unit_price DESC
                LIMIT 10
            """,
            "viz_type": "table",
            "viz_title": "Precios encontrados para '{captured}'"
        },
        "params_mapper": lambda captured: f"%{captured}%"
    },

    # -------------------------------------------------------------------------
    # 5. ANÁLISIS DE VENTAS (KPIs)
    # -------------------------------------------------------------------------
    # Ventas por Canal
    {
        "patterns": [
            r"^ventas? por canal(?:es)?$",
            r"^ventas? (?:online|en linea|fisicas?)$",
            r"^canal(?:es)? con (?:mas|mayor) ventas?$"
        ],
        "response_template": {
            "sql": """
                SELECT sales_channel, SUM(total) as total_ventas, COUNT(sale_id) as transacciones
                FROM {TABLE_SALES}
                GROUP BY sales_channel
                ORDER BY total_ventas DESC
            """,
            "viz_type": "pie",
            "viz_title": "Ventas por Canal"
        }
    },
    # Ventas por Método de Pago
    {
        "patterns": [
            r"^ventas? por (?:metodo|forma) de pago$",
            r"^como paga(?:n)? (?:mas|menos) (?:los clientes)?$"
        ],
        "response_template": {
            "sql": """
                SELECT payment_method, SUM(total) as total_ventas
                FROM {TABLE_SALES}
                GROUP BY payment_method
                ORDER BY total_ventas DESC
            """,
            "viz_type": "bar",
            "viz_title": "Ventas por Método de Pago"
        }
    },
    # Ventas por Categoría
    {
        "patterns": [
            r"^ventas? por categor[ií]a$",
            r"^rendimiento por categor[ií]a$"
        ],
        "response_template": {
            "sql": """
                SELECT p.category, SUM(f.total) as total_ventas
                FROM {TABLE_SALES} f
                JOIN {TABLE_PROD} p ON f.product_id = p.product_id
                GROUP BY p.category
                ORDER BY total_ventas DESC
            """,
            "viz_type": "bar",
            "viz_title": "Ventas por Categoría"
        }
    },
    # Ventas por Región
    {
        "patterns": [
            r"^ventas? por regi[oó]n$",
            r"^ventas? por zona$"
        ],
        "response_template": {
            "sql": """
                SELECT c.region, SUM(f.total) as total_ventas
                FROM {TABLE_SALES} f
                JOIN {TABLE_CUST} c ON f.customer_id = c.customer_id
                GROUP BY c.region
                ORDER BY total_ventas DESC
            """,
            "viz_type": "pie",
            "viz_title": "Distribución de Ventas por Región"
        }
    },

    # -------------------------------------------------------------------------
    # 6. RANKINGS DE PRODUCTOS
    # -------------------------------------------------------------------------
    # Top Unidades (Cantidad - Más específico, va primero)
    {
        "patterns": [
            r"^top (\d+) productos? (?:mas|más) vendidos?$",
            r"^cuales son los (\d+) productos? que (?:mas|más) salen?$"
        ],
        "response_template": {
            "sql": """
                SELECT p.product_name, SUM(f.quantity) as unidades_vendidas
                FROM {TABLE_SALES} f 
                JOIN {TABLE_PROD} p ON f.product_id = p.product_id 
                GROUP BY p.product_name 
                ORDER BY unidades_vendidas DESC 
                LIMIT %(p1)s
            """,
            "viz_type": "bar",
            "viz_title": "Top {captured} Productos (por Unidades)"
        },
        "params_mapper": lambda captured: int(captured)
    },
    # Top Ingresos (Dinero - Más genérico)
    {
        "patterns": [
            r"^top (\d+) (?:de )?productos?$",
            r"^(?:los|las) (\d+) (?:mejores|peores) productos?$"
        ],
        "response_template": {
            "sql": """
                SELECT p.product_name, SUM(f.total) as ventas_totales 
                FROM {TABLE_SALES} f 
                JOIN {TABLE_PROD} p ON f.product_id = p.product_id 
                GROUP BY p.product_name 
                ORDER BY ventas_totales DESC 
                LIMIT %(p1)s
            """,
            "viz_type": "bar",
            "viz_title": "Top {captured} Productos (por Ingresos)"
        },
        "params_mapper": lambda captured: int(captured)
    },

    # -------------------------------------------------------------------------
    # 7. ANÁLISIS TEMPORAL
    # -------------------------------------------------------------------------
    {
        "patterns": [
            r"^ventas?.*(\d{4})$", 
            r"^ingresos?.*(\d{4})$"
        ],
        "response_template": {
            "sql": """
                SELECT TO_CHAR({COL_DATE}, 'YYYY-MM') as mes, SUM(total) as ventas 
                FROM {TABLE_SALES} 
                WHERE EXTRACT(YEAR FROM {COL_DATE}) = %(p1)s 
                GROUP BY mes 
                ORDER BY mes ASC
            """,
            "viz_type": "line",
            "viz_title": "Evolución Ventas {captured}"
        },
        "params_mapper": lambda captured: int(captured)
    },

    # -------------------------------------------------------------------------
    # 8. BÚSQUEDA GENÉRICA (Fallback inteligente)
    # -------------------------------------------------------------------------
    {
        "patterns": [
            r"^ventas (?:en |de |del )?(.+)$", 
            r"^ingresos (?:en |de |del )?(.+)$",
            r"^como va (?:la zona |la region |el producto )?(.+)$"
        ],
        "response_template": {
            "sql": """
                SELECT 
                    p.product_name, 
                    c.region,
                    SUM(f.total) as ventas
                FROM {TABLE_SALES} f
                JOIN {TABLE_PROD} p ON f.product_id = p.product_id
                JOIN {TABLE_CUST} c ON f.customer_id = c.customer_id
                WHERE unaccent(p.product_name) ILIKE unaccent(%(p1)s) 
                   OR unaccent(p.category) ILIKE unaccent(%(p1)s) 
                   OR unaccent(c.region) ILIKE unaccent(%(p1)s)
                GROUP BY p.product_name, c.region
                ORDER BY ventas DESC
                LIMIT 20
            """,
            "viz_type": "table",
            "viz_title": "Resultados de búsqueda para '{captured}'"
        },
        "params_mapper": lambda captured: f"%{captured}%"
    },
    
    # -------------------------------------------------------------------------
    # 9. TOTAL GENERAL (Comodín final)
    # -------------------------------------------------------------------------
    {
        "patterns": [r"^ventas? totales?$", r"^cuanto vendimos (?:en total)?$"],
        "response_template": {
            "sql": "SELECT SUM(total) as total_ventas FROM {TABLE_SALES}",
            "viz_type": "number",
            "viz_title": "Ingresos Totales Históricos"
        }
    }
]

def check_rules(question: str) -> Optional[Dict[str, Any]]:
    q_clean = normalize_text(question)
    
    for rule in RULES_CATALOG:
        for pattern in rule["patterns"]:
            match = re.search(pattern, q_clean)
            if match:
                template = rule["response_template"]
                result = template.copy()

                # Inyectamos nombres de tablas
                result["sql"] = result["sql"].format(
                    TABLE_SALES=TABLE_SALES,
                    TABLE_PROD=TABLE_PROD,
                    TABLE_CUST=TABLE_CUST,
                    TABLE_EMP=TABLE_EMP,
                    COL_DATE=COL_DATE
                )

                result["params"] = {} 

                # Si la regla captura un parámetro (ej: el año o el nombre)
                if match.groups() and "params_mapper" in rule:
                    try:
                        captured_text = match.group(1)
                        # Inyectamos el texto capturado en el título del gráfico
                        if "{captured}" in result["viz_title"]:
                            result["viz_title"] = result["viz_title"].format(captured=captured_text.title())
                        
                        # Convertimos el parámetro (int, string con %, etc.)
                        param_value = rule["params_mapper"](captured_text)
                        result["params"] = {"p1": param_value}
                    except ValueError:
                        continue 

                return result
    return None