import yaml
import os
import sys

# Ajuste para importar módulos hermanos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.semantic.semantic_types import SemanticModel

# --- Función de Carga ---

def load_semantic_model() -> SemanticModel:
    """
    Lee el archivo semantic_model.yaml y lo convierte en un objeto Pydantic validado.
    """
    # Ruta absoluta al archivo YAML
    current_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(current_dir, "semantic_model.yaml")

    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"❌ ERROR CRÍTICO: No encuentro el archivo {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"❌ Error de sintaxis en el YAML: {e}")

    # Validación automática con Pydantic
    try:
        # Aquí Pydantic transforma el diccionario en objetos.
        # Convierte 'schema' (YAML) -> 'schema_name' (Python) automáticamente
        model = SemanticModel(**data)
        return model
    except Exception as e:
        print(f"❌ El YAML no cumple con el esquema esperado en types.py")
        raise e

# --- Bloque de prueba (Solo se ejecuta si corres este archivo directamente) ---
if __name__ == "__main__":
    try:
        model = load_semantic_model()
        print("✅ ¡Carga Exitosa!")
        print(f"   📊 Tablas detectadas: {len(model.tables)}")
        for t in model.tables:
            print(f"      - {t.name} ({len(t.columns)} columnas)")
        print(f"   🔗 Relaciones: {len(model.relationships)}")
    except Exception as e:
        print(f"❌ Falló la carga: {e}")