# FastAPI app + include_router
from fastapi import FastAPI
from app.core.logging import setup_logging
from app.api.routes.health import router as health_router
from app.api.routes.query import router as query_router
from app.api.routes.audit import router as audit_router

setup_logging()
app = FastAPI(title="Desafio de Tripulaciones API", version="1.0")

# Ruta raíz (Opcional, pero recomendada para no ver un 404 al entrar al home)
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