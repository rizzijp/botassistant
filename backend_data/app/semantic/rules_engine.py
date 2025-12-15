import re
import unicodedata
from typing import Optional, Dict, Any

def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', text)

# --- CATÁLOGO DE REGLAS (FASE 2.5: REFINED & ANCHORED) ---
# CAMBIOS CLAVE:
# 1. Agregamos '^' (inicio) y '$' (fin) a los regex para evitar "falsos positivos" en frases largas.
# 2. Cambiamos 'pie' por 'bar' en regiones (más legible).

RULES_CATALOG = [
    # --- A. TOP N (Estricto) ---
    {
        "patterns": [
            r"^top (\d+) (?:de )?productos?$",
            r"^(?:los|las) (\d+) (?:mejores|peores) productos?$"
        ],
        "response_template": {
            "sql": "SELECT p.product_name, SUM(f.total) as ventas FROM curated.fact_sales f JOIN curated.dim_product p ON f.product_id = p.product_id GROUP BY p.product_name ORDER BY ventas DESC LIMIT %(p1)s",
            "viz_type": "bar",
            "viz_title": "Top {captured} Productos"
        },
        "params_mapper": lambda captured: int(captured)
    },
    
    # --- B. FILTROS POR AÑO (Estricto) ---
    {
        "patterns": [
            r"^ventas?.*(\d{4})$", 
            r"^ingresos?.*(\d{4})$"
        ],
        "response_template": {
            "sql": "SELECT TO_CHAR(sale_date, 'YYYY-MM') as mes, SUM(total) as ventas FROM curated.fact_sales WHERE year = %(p1)s GROUP BY mes ORDER BY mes ASC",
            "viz_type": "line",
            "viz_title": "Evolución Ventas {captured}"
        },
        "params_mapper": lambda captured: int(captured)
    },

    # --- C. BÚSQUEDA ESPECÍFICA (La que causaba problemas) ---
    # Usamos anclas para que NO atrape "Diferencia de ventas..."
    {
        "patterns": [
            r"^ventas (?:en |de |del )?(.+)$", 
            r"^ingresos (?:en |de |del )?(.+)$",
            r"^como va (?:la zona |la region |el producto )?(.+)$"
        ],
        "response_template": {
            "sql": """
                SELECT p.product_name, SUM(f.total) as ventas
                FROM curated.fact_sales f
                JOIN curated.dim_product p ON f.product_id = p.product_id
                JOIN curated.dim_customer c ON f.customer_id = c.customer_id
                -- Buscamos en Producto O en Región O en Cliente (Búsqueda Universal)
                WHERE p.product_name ILIKE %(p1)s 
                   OR p.category ILIKE %(p1)s 
                   OR c.region ILIKE %(p1)s
                GROUP BY p.product_name
                ORDER BY ventas DESC
                LIMIT 20
            """,
            "viz_type": "bar", # Cambiado a BAR por ser más seguro
            "viz_title": "Resultados para '{captured}'"
        },
        "params_mapper": lambda captured: f"%{captured}%"
    },

    # --- D. REGLAS ESTÁTICAS (Sin cambios) ---
    {
        "patterns": [r"^hola$", r"^buenos dias$"],
        "response_template": {
            "sql": "SELECT '¡Hola! Soy tu asistente.' as mensaje",
            "viz_type": "number",
            "viz_title": "Saludo"
        }
    },
    {
        "patterns": [r"^ventas? totales?$", r"^cuanto vendimos$"],
        "response_template": {
            "sql": "SELECT SUM(total) as total_ventas FROM curated.fact_sales",
            "viz_type": "number",
            "viz_title": "Ingresos Totales"
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
                result["params"] = {} 

                if match.groups() and "params_mapper" in rule:
                    try:
                        captured_text = match.group(1)
                        if "{captured}" in result["viz_title"]:
                            result["viz_title"] = result["viz_title"].format(captured=captured_text.title())
                        
                        param_value = rule["params_mapper"](captured_text)
                        result["params"] = {"p1": param_value}
                    except ValueError:
                        continue 

                return result
    return None