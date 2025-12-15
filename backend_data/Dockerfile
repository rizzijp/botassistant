# 1. Usamos una imagen base de Python ligera y segura
FROM python:3.11-slim

# 2. Evitamos que Python genere archivos .pyc y activamos logs inmediatos
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Directorio de trabajo dentro del contenedor
WORKDIR /code

# 4. Instalamos dependencias del sistema necesarias (opcional, pero recomendado para Postgres)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 5. Copiamos los requerimientos primero (para aprovechar la caché de Docker)
COPY ./requirements.txt /code/requirements.txt

# 6. Instalamos las librerías de Python
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 7. Copiamos el código de tu aplicación a la carpeta /code/app
COPY ./app /code/app

# 8. Exponemos el puerto 8000
EXPOSE 8000

# 9. Comando para arrancar el servidor
# Ajusta "app.main:app" si tu archivo principal tiene otro nombre
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]