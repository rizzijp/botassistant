from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from query_plan import VizType

# --- MODELOS DE DATOS (DTOs) ---
# Definimos estrictamente qué entra y qué sale de la API.

class QueryRequest(BaseModel):
    message: str = Field(..., description="La pregunta del usuario en lenguaje natural")
    session_id: str = Field(..., description="Identificador único de la sesión")
    user_id: int = Field(..., description="Identificador del usuario")
    role: str = Field(default="user", description="Rol del usuario (ej: gerente, admin)")
    model: Optional[str] = Field(default="llama-3", description="Modelo de IA a usar")

class QueryResponse(BaseModel):
    #user_id: int se puede agregar cuando se implemente el audit log
    exito: bool
    session_id: str
    mensaje: str
    sql_generado: Optional[str] = None
    datos: List[Dict[str, Any]] = []
    columnas: List[str] = []
    total_filas: int = 0
    tipo_grafica: Optional[VizType] = None
    tiene_grafica: bool = False
    grafica_base64: Optional[str] = None