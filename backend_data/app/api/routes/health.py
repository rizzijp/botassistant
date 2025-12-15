from fastapi import APIRouter

router = APIRouter()

@router.get("/")  # Se convertirá en /health gracias al main.py
def health_check():
    """
    Endpoint para monitoreo. Devuelve 200 OK si el backend está vivo.
    """
    return {"status": "ok", "service": "data-backend"}