# Usamos una imagen ligera de Python
FROM python:3.11-slim

# Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos primero los requerimientos para aprovechar la caché de Docker
COPY requirements.txt .

# Instalamos las librerías necesarias
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código (tu app_dashboard.py)
COPY front_test.py .

# Comando para iniciar Streamlit
# IMPORTANTE: Render asigna un puerto dinámico en la variable $PORT.
# Usamos 'sh -c' para poder leer esa variable correctamente.
CMD sh -c "streamlit run front_test.py --server.port=${PORT:-8501} --server.address=0.0.0.0"