FROM python:3.9-slim-buster

WORKDIR /app

# Copiar los archivos de requisitos primero para aprovechar la caché de Docker
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copiar el resto de archivos
COPY main.py slskd.py betanin.py example_config.py ./

# Configurar PYTHONPATH para que encuentre los módulos en el directorio actual
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Verificar que config.py existe, si no, crear uno a partir de example_config.py
CMD ["python", "-c", "import os; os.system('if [ ! -f config.py ]; then cp example_config.py config.py; fi'); os.system('python main.py')"]