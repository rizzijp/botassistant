import os
from dotenv import load_dotenv

load_dotenv()

# Define modelos hardcodeados. 
# Mejora: Debería usar pydantic-settings para validar variables de entorno y permitir cambiar modelos sin tocar código.
# --- DICCIONARIO MAESTRO DE MODELOS ---
# El formato debe ser SIEMPRE: "alias": "proveedor/nombre_tecnico"
MAPA_MODELOS = {
    #"gpt-4": "openai/gpt-4-turbo",
    #"gpt-3.5": "openai/gpt-3.5-turbo",
    "llama-3": "groq/llama-3.3-70b-versatile",   # Modelo equilibrado (Potente y Rápido)
    "llama-fast": "groq/llama-3.1-8b-instant", # Modelo "Turbo" (Para cosas ultra-rápidas)
    "mixtral": "groq/mixtral-8x7b-32768",
    #"claude-3": "anthropic/claude-3-opus-20240229", (Requiere librería distinta, lo vemos luego)
    "gemini-pro": "gemini/gemini-1.5-pro",   # Modelo Potente de Google
    "gemini-flash": "gemini/gemini-1.5-flash" # Modelo Rápido de Goog
}

# --- MODELO POR DEFECTO ---
#MODELO_PRINCIPAL = "llama-3" # Usamos el ALIAS, no el nombre técnico
MODELO_PRINCIPAL = "gemini-flash"