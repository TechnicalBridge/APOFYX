# =============================================================================
#  APOFYX — imagen de la aplicacion Django
# =============================================================================
#  Imagen de DESARROLLO: incluye el compilador porque mysqlclient se compila
#  al instalarse. Para produccion convendria una construccion en dos etapas
#  que descarte build-essential de la imagen final.
#
#  No se construye sola: la orquesta docker-compose.yml, bajo el perfil "app".
#      docker compose --profile app up -d --build
# =============================================================================

FROM python:3.14-slim

# PYTHONDONTWRITEBYTECODE: no dejar archivos .pyc en el volumen montado.
# PYTHONUNBUFFERED: que los logs de Django salgan al instante, sin buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# mysqlclient no trae rueda precompilada para esta plataforma: necesita el
# compilador de C y las cabeceras del cliente de MySQL.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Las dependencias se copian primero y solas: mientras requirements.txt no
# cambie, Docker reutiliza esta capa y no vuelve a instalar nada.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# 0.0.0.0 y no 127.0.0.1: si escucha solo en loopback, el puerto publicado
# por compose no llega a ningun lado.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
