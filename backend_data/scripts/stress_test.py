import requests
import json
import time

BASE_URL = "http://localhost:8000/api/ask"
USER_ID = 999 # Usuario de pruebas

scenarios = [
    {"name": "1. Regla Estática", "q": "hola"},
    {"name": "2. Regla Dinámica (Texto)", "q": "Ventas de Monitor"},
    {"name": "3. Regla Dinámica (Numérica)", "q": "Top 3 productos"},
    {"name": "4. Fallback LLM", "q": "Diferencia de ventas entre 2023 y 2024"},
    {"name": "5. Seguridad (Injection)", "q": "Ventas de A'; DROP TABLE raw.users; --"},
]

print(f"🔥 INICIANDO BATERÍA DE PRUEBAS CONTRA {BASE_URL}...\n")

for test in scenarios:
    print(f"👉 Probando: {test['name']} | Query: '{test['q']}'")
    start = time.time()
    
    try:
        response = requests.post(BASE_URL, json={
            "user_id": USER_ID,
            "message": test['q'],
            "session_id": "test_session_id",
            "role": "admin"
        })
        
        duration = round(time.time() - start, 2)
        
        if response.status_code == 200:
            data = response.json()
            viz = data.get("viz_type", "N/A")
            rows = data.get("row_count", 0)
            title = data.get("viz_title", "Sin título")
            print(f"   ✅ OK ({duration}s) | Rows: {rows} | Viz: {viz} | Title: {title}")
        else:
            print(f"   ❌ ERROR {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")
    
    print("-" * 50)