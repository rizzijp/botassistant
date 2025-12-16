from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# Definimos los tipos de gráficos válidos para que el Front no se rompa
VizType = Literal["bar", "line", "pie", "number", "table", "scatter"]

# --- Estructuras para el Plan de Consulta (QueryPlan) ---

class Filter(BaseModel):
    column: str       # Ej: "region"
    operator: str     # Ej: "=", ">", "ilike"
    value: str | int | float  # Ej: "Madrid"

class QueryPlan(BaseModel):
    metrics: List[str]      # Ej: ["total_sales"]
    dimensions: List[str]   # Ej: ["category"]
    filters: List[Filter]   # Ej: region = 'Madrid'
    limit: Optional[int] = None
    viz_type: VizType = Field(
        default="table", 
        description="Tipo de gráfico recomendado por el LLM"
    )
    viz_title: Optional[str] = Field(
        default=None, 
        description="Título descriptivo para el gráfico"
    )




