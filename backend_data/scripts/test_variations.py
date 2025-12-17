import requests
import pandas as pd
import time
from datetime import datetime

# --- CONFIGURACIÓN ---
# Ajusta la URL si usas Render o Localhost
#API_URL = "https://botassistant-api.onrender.com/api/ask" 
API_URL = "http://127.0.0.1:8000/api/ask"
USER_ID = 888
SESSION_ID = "stress_test_v2"

# --- NUEVOS CASOS DE PRUEBA (Variaciones y Complejidad) ---
TEST_CASES = [
    # --- GRUPO A: LENGUAJE NATURAL Y SINÓNIMOS (Reglas/Static) ---
    "Ey buenas",                 # Var. de Hola
    "Ayuda por favor",           # Var. de Ayuda
    "Necesito asistencia",       # Var. de Ayuda
    
    # --- GRUPO E: VENTAS COMPLEJAS (LLM Puro) ---
    "Ventas de monitores en el primer trimestre de 2024", # Q1
    "Ventas de zapatillas vs monitores en 2023",          # Comparación
    "Cual fue el mes con mas ventas del año pasado",      # Agregación temporal
    "Promedio de venta por cliente en Mexico",            # Filtro doble + KPI
    "Total vendido en efectivo vs tarjeta",               # Pivoteo (si el LLM es listo)
    "Ventas de productos de la categoria Hogar en España",# Join triple (Ventas-Prod-Cliente)
]

results = []
print(f"🚀 Iniciando STRESS TEST ({len(TEST_CASES)} casos complejos)...")
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
        
        # Timeout un poco más alto para las complejas del LLM
        response = requests.post(API_URL, json=payload, timeout=20) 
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            sql = data.get("sql_generado", "")
            rows = len(data.get("datos", []))
            viz = data.get("viz_title", "N/A") or "N/A"
            msg = data.get("mensaje", "")[:30] # Primeros caracteres del mensaje
            
            # --- DETECCIÓN MEJORADA DE MOTOR ---
            if sql is None:
                engine_real = "💬 CHAT/STATIC"  # Saludos o Anti-Chitchat
            elif "/* ⚡ REGLA */" in sql:
                engine_real = "⚡ REGLAS"       # Reglas SQL
            else:
                engine_real = "🤖 LLM"          # Generación dinámica
            
            print(f"✅ ({elapsed:.2f}s) {engine_real} - Filas: {rows}")
            
            results.append({
                "question": question,
                "status": "OK",
                "engine": engine_real,
                "rows": rows,
                "time_sec": round(elapsed, 2),
                "sql_snippet": str(sql)[:40].replace("\n", " ") + "..." if sql else "N/A",
                "viz_title": viz
            })
        else:
            print(f"❌ Error {response.status_code}")
            results.append({"question": question, "status": f"ERROR {response.status_code}", "engine": "ERROR", "rows": 0})

    except Exception as e:
        print(f"❌ Excepción: {str(e)[:50]}")
        results.append({"question": question, "status": "EXCEPTION", "engine": "ERROR", "rows": 0})

# Guardar reporte
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
filename = f"stress_test_{timestamp}.csv"
df = pd.DataFrame(results)

df.to_csv(filename, index=False)

print("\n" + "="*50)
print(f"📊 REPORTE DE ESTRÉS GENERADO: {filename}")
print("="*50)
print(df["engine"].value_counts())