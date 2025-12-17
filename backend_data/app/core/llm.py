import os
from litellm import completion
from app.core.config import MAPA_MODELOS, MODELO_PRINCIPAL
from app.core.logging import logger
import time

def resolve_model_name(model_alias: str) -> str:
    """
    Traduce un alias (ej: 'llama-3') al nombre técnico que requiere LiteLLM
    (ej: 'groq/llama3-70b-8192').
    """
    # Si el alias está en nuestro mapa, usamos el nombre técnico
    if model_alias in MAPA_MODELOS:
        return MAPA_MODELOS[model_alias]
    
    # Si no, asumimos que ya nos pasaron un nombre técnico válido
    return model_alias

def call_llm(system_prompt: str, user_prompt: str, model_alias: str = MODELO_PRINCIPAL) -> str:
    """
    Llamada universal a cualquier LLM usando LiteLLM.
    Maneja automáticamente OpenAI, Groq, Anthropic, etc.
    """
    model_name = resolve_model_name(model_alias)

    messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    # Intentos maximos
    max_retries = 2

    for attempt in range(max_retries):
        try:
            logger.info(f"🔌 [LLM] Conectando con: {model_name} (Intento {attempt + 1})")
            
            response = completion(
                model=model_name,
                messages=messages,
            temperature=0.0
        )
        
            # Si tiene éxito, devolvemos la respuesta
            return response.choices[0].message.content

        except Exception as e:
            error_str = str(e).lower()
        
            # Si es un error de Rate Limit y no es el último intento
            if "rate limit" in error_str and attempt < max_retries - 1:
                wait_time = 5 * (attempt + 1) # Espera 5s, 10s, 15s...
                logger.warning(f"⏳ [RATE LIMIT] Esperando {wait_time}s para reintentar...")
                time.sleep(wait_time)
                continue
        
            # Si es otro error o se acabaron los intentos
            logger.error(f"❌ Error crítico llamando al LLM ({model_alias}): {e}")
            raise e