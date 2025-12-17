import requests
import pandas as pd
import time
from datetime import datetime

# --- CONFIGURACIÓN ---
API_URL = "https://botassistant-api.onrender.com/api/ask"
USER_ID = 999
SESSION_ID = "test_automation_50"

# --- LOS 50 CASOS DE PRUEBA ---
TEST_CASES = [
    # --- GRUPO A: SALUDOS (Reglas) ---
    "Hola",
    "Buenos dias",
    "Que tal",

    # --- GRUPO B: RRHH (Reglas) ---
    "Salario de Javier Torres",
    "Cuanto gana Sofia Ruiz",
    "Puesto de Andrea Reyes",
    "Cargo de Diego Herrera",
    "Quien es Carlos Perez",
    "Datos de Lucia Castillo",
    "Top 5 salarios",
    "Los 3 empleados con mayor sueldo",

    # --- GRUPO C: CLIENTES (Reglas) ---
    "Cliente Roberto Rivas",
    "Datos del cliente Marina Garcia",
    "Contacto de Luis Lopez",
    "Buscar cliente Andrea Santos",

    # --- GRUPO D: PRECIOS (Reglas) ---
    "Precio del Monitor Moderno",
    "Cuanto cuesta el Smartphone Slim",
    "Valor de la Silla Vintage",
    "Precio de zapatillas",
    "Cuanto cuesta el mouse",

    # --- GRUPO E: KPIs DE VENTAS (Reglas) ---
    "Ventas por canal",
    "Ventas online",
    "Ventas por metodo de pago",
    "Como pagan mas los clientes",
    "Ventas por categoria",
    "Rendimiento por categoria",
    "Ventas por region",
    "Ventas por zona",
    "Ventas totales", # ¡Esta es crítica que salga con Regla!
    "Cuanto vendimos en total",

    # --- GRUPO F: RANKINGS PRODUCTOS (Reglas) ---
    "Top 5 productos mas vendidos",
    "Cuales son los 10 productos que mas salen",
    "Top 5 productos",
    "Los 3 mejores productos",

    # --- GRUPO G: FECHAS SIMPLES (Reglas) ---
    "Ventas 2024",
    "Ingresos 2023",

    # --- GRUPO H: BÚSQUEDA GENÉRICA (Reglas - Fallback) ---
    "Ventas de monitores",
    "Como va la zona Norte",
    "Ingresos de laptops",

    # --- GRUPO I: COMPLEJOS PARA IA (LLM - No deberían tener la marca) ---
    "Ventas de monitores en enero 2024",
    "Promedio de ventas por dia",
    "Clientes de Mexico que compraron monitores",
    "Empleados del departamento TI que ganan mas de 3000",
    "Comparar ventas entre 2023 y 2024",
    "Cual fue la venta mas alta registrada",
    "Cuantos clientes unicos tenemos",
    "Ticket promedio de venta online",
    "Productos que nunca se han vendido",
    "Ventas totales agrupadas por vendedor",
    "Dame un resumen de las ventas de ayer"
]

results = []
print(f"🚀 Iniciando prueba masiva de {len(TEST_CASES)} casos...")
print(f"📡 Conectando a: {API_URL}\n")

for i, question in enumerate(TEST_CASES):
    print(f"[{i+1}/{len(TEST_CASES)}] {question}...", end=" ")
    
    try:
        start = time.time()
        payload = {
            "user_id": USER_ID,
            "session_id": SESSION_ID,
            "message": question,
            "model": "llama-3"
        }
        
        response = requests.post(API_URL, json=payload)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            sql = data.get("sql_generado", "") or "" # Evitar None
            rows = len(data.get("datos", []))
            viz = data.get("viz_title", "N/A")
            
            # --- DETECCIÓN INFALIBLE POR MARCA SQL ---
            if "/* ⚡ REGLA */" in sql:
                engine_real = "⚡ REGLAS"
            else:
                engine_real = "🤖 LLM"
            
            # Imprimir resultado en consola
            print(f"✅ ({elapsed:.2f}s) {engine_real} - Filas: {rows}")
            
            results.append({
                "question": question,
                "status": "OK",
                "engine": engine_real, # La verdad absoluta basada en tu inyección
                "rows": rows,
                "time_sec": round(elapsed, 2),
                "sql_snippet": sql[:50].replace("\n", " ") + "...",
                "sql_full": sql,  # Full SQL, not truncated
                "viz_type": data.get("tipo_grafica", "N/A"),
                "viz_title": viz,
                "tiene_grafica": data.get("tiene_grafica", False),
                "mensaje": data.get("mensaje", ""),
                "total_filas": data.get("total_filas", 0),
                "columnas": ",".join(data.get("columnas", [])),
                # Save full JSON for debugging
                "response_json": json.dumps(data)
            })
        else:
            print(f"❌ Error {response.status_code}")
            results.append({"question": question, "status": "ERROR", "engine": "ERROR", "rows": 0})

    except Exception as e:
        print(f"❌ Excepción: {e}")
        results.append({"question": question, "status": "EXCEPTION", "engine": "ERROR", "rows": 0})

# Guardar reporte
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
filename = f"test_results_50_{timestamp}.csv"
df = pd.DataFrame(results)

df.to_csv(filename, index=False)

print("\n" + "="*50)
print(f"📊 REPORTE GENERADO: {filename}")
print("="*50)
# Mostramos un resumen rápido de conteo
print(df["engine"].value_counts())
print("\nMuestra de resultados:")
print(df[["question", "engine", "rows"]].head(10))