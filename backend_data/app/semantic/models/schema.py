from pydantic import BaseModel, Field
from typing import List, Optional, Literal

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