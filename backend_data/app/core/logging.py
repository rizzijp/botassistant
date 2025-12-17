import logging
import sys

# 1. Definir la variable 'logger' que todos intentan importar
logger = logging.getLogger("app")

def setup_logging(level=logging.INFO):
    """Configura el formato y handlers del logger"""
    # Limpiar handlers previos si existen para evitar duplicados
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)
            
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            # logging.FileHandler('app.log')  # Opcional
        ]
    )
    logger.setLevel(level)

# 2. Inicializar configuración por defecto al importar
setup_logging()