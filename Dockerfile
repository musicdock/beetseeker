FROM python:3.9-slim-buster

WORKDIR /app

# Copiar los archivos de requisitos primero para aprovechar la caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY main.py slskd.py betanin.py example_config.py ./

# Puerto para la interfaz de depuración
EXPOSE 8347

# Configuración del entorno - corregida para evitar la advertencia
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"

# Asegurar que existe un archivo de configuración
RUN echo '#!/bin/sh\n\
if [ ! -f /app/config.py ]; then\n\
  echo "No config.py found, using example_config.py"\n\
  cp /app/example_config.py /app/config.py\n\
fi\n\
python /app/main.py\n' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Punto de entrada
ENTRYPOINT ["/app/entrypoint.sh"]