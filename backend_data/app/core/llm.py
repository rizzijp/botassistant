import os
from litellm import completion
from app.core.config import MAPA_MODELOS, MODELO_PRINCIPAL

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
    try:
        # 1. Resolver el nombre real del modelo
        model_name = resolve_model_name(model_alias)
        
        print(f"🔌 [LLM] Conectando con: {model_name}")

        # 2. LiteLLM hace la magia
        # Busca automáticamente la API KEY en las variables de entorno según el prefijo
        response = completion(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0
        )
        
        # 3. Retornar texto limpio
        return response.choices[0].message.content

    except Exception as e:
        print(f"❌ Error crítico llamando al LLM ({model_alias}): {e}")
        raise e