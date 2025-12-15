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


# --- MODELOS DE DATOS (DTOs) ---
# Definimos estrictamente qué entra y qué sale de la API.

#class QueryRequest(BaseModel):
#    user_id: int = Field(..., description="ID del usuario que hace la consulta (para auditoría)")
#    question: str = Field(..., description="La pregunta en lenguaje natural")
#    model: Optional[str] = Field(default=MODELO_PRINCIPAL, description="Alias del modelo a usar (ej: 'gpt-4', 'llama-3')")

class QueryRequest(BaseModel):
    message: str = Field(..., description="La pregunta del usuario en lenguaje natural")
    session_id: str = Field(..., description="Identificador único de la sesión")
    user_id: int = Field(..., description="Identificador del usuario")
    role: str = Field(default="user", description="Rol del usuario (ej: gerente, admin)")
    model: Optional[str] = Field(default=MODELO_PRINCIPAL, description="Modelo de IA a usar")

#class QueryResponse(BaseModel):
#    user_id: int
#    question: str
#    sql: str
#    data: List[Dict[str, Any]] # Resultado de la query
#    columns: List[str]         # Nombres de las columnas para el Frontend
#    row_count: int
#    execution_time: float      # Tiempo que tardó en segundos
#    viz_type: VizType = Field(default="table")
#    viz_title: Optional[str] = None

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

