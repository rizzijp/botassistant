# FastAPI app + include_router
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.logging import setup_logging
from app.api.routes.health import router as health_router
from app.api.routes.query import router as query_router
from app.api.routes.audit import router as audit_router
from fastapi.middleware.cors import CORSMiddleware


setup_logging()
app = FastAPI(title="Desafio de Tripulaciones API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://globo-market.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 👇 AQUÍ AGREGAMOS EL MANEJADOR DE ERROR 422 PERSONALIZADO 👇 ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Intercepta los errores de validación (422) y devuelve el JSON
    con el formato unificado del proyecto en lugar del estándar de FastAPI.
    """
    # 1. Extraer los detalles del error para crear un mensaje legible
    errores_lista = []
    for error in exc.errors():
        # 'loc' indica dónde está el error (ej: body -> message)
        campo = " -> ".join(str(x) for x in error.get("loc", []))
        mensaje = error.get("msg", "Valor inválido")
        errores_lista.append(f"[{campo}]: {mensaje}")
    
    mensaje_final = f"Error de validación: {'; '.join(errores_lista)}"

    # 2. Devolver la respuesta con TU esquema exacto
    return JSONResponse(
        status_code=422,
        content={
            "exito": False,
            "session_id": None, # No hay sesión porque falló la entrada
            "mensaje": mensaje_final,
            "sql_generado": None,
            "datos": [],
            "columnas": [],
            "total_filas": 0,
            "tipo_grafica": None,
            "tiene_grafica": False,
            "grafica_base64": None
        }
    )
# ------------------------------------------------------------------


# Ruta raíz
@app.get("/", tags=["home"])
def home():
    return {"message": "API Online. Documentación en /docs"}

# Integración de Routers
# 1. Health -> Queda en /health
app.include_router(health_router, prefix="/health", tags=["health"])

# 2. Query -> Queda en /api/ask
app.include_router(query_router, prefix="/api", tags=["query"])

# 3. Audit -> Queda en /audit/logs
app.include_router(audit_router, prefix="/audit", tags=["audit"])