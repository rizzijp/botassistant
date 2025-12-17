import requests
import pandas as pd
import time
from datetime import datetime

# --- CONFIGURACIÓN ---
#API_URL = "https://botassistant-api.onrender.com/api/ask"
API_URL = "http://127.0.0.1:8000/api/ask"
USER_ID = 999
SESSION_ID = "test_automation_50"

# --- LOS 50 CASOS DE PRUEBA ---
TEST_CASES = [
    # --- GRUPO A: SALUDOS (Reglas) ---
    "Hola",
    "Buenos dias",
    "Que tal",


    # --- GRUPO I: COMPLEJOS PARA IA (LLM - No deberían tener la marca) ---
    "Ventas de monitores en febrero de 2023",
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
            "message": question
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
                "viz_title": viz
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