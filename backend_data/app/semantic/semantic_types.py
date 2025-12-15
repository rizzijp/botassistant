from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# Definimos los tipos de gráficos válidos para que el Front no se rompa
VizType = Literal["bar", "line", "pie", "number", "table", "scatter"]

# --- MODELOS DEL MAPA SEMÁNTICO (Representan tu YAML) ---

class ColumnDef(BaseModel):
    name: str
    type: str  # text, integer, date, etc.
    description: Optional[str] = None

class MetricDef(BaseModel):
    name: str
    sql: str
    description: Optional[str] = None

class TableDef(BaseModel):
    name: str
    schema_name: str = Field(alias="schema") # Mapea "schema" del YAML a "schema_name" en Python
    description: Optional[str] = None
    columns: List[ColumnDef]
    metrics: Optional[List[MetricDef]] = []

class RelationDef(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    type: str = "many_to_one"

class SemanticModel(BaseModel):
    tables: List[TableDef]
    relationships: List[RelationDef]

# --- NUEVO: Estructuras para el Plan de Consulta (QueryPlan) ---

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