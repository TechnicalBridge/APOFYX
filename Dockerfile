# =============================================================================
#  APOFYX — la aplicacion Django
# =============================================================================
#  Dos etapas. La primera instala las dependencias, y para eso necesita el
#  compilador de C, porque mysqlclient no trae rueda precompilada. La segunda
#  se queda con el entorno ya instalado y sin compilador: unos 300 MB menos, y
#  sin un compilador dentro del contenedor que sirva a quien no deba.
#
#  No se construye sola: la orquesta docker-compose.yml, bajo el perfil "app".
#      docker compose --profile app up -d --build
# =============================================================================

FROM python:3.14-slim AS dependencias

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

#  Un entorno virtual y no el Python del sistema: asi la segunda etapa se lo
#  lleva entero copiando una sola carpeta.
RUN python -m venv /opt/entorno
ENV PATH="/opt/entorno/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir gunicorn==23.0.0


# -----------------------------------------------------------------------------

FROM python:3.14-slim

#  PYTHONDONTWRITEBYTECODE: no dejar .pyc sueltos.
#  PYTHONUNBUFFERED: que los logs salgan al instante y no cuando se llene el buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/entorno/bin:$PATH"

#  mysqlclient ya esta compilado, pero necesita la libreria del cliente en
#  tiempo de ejecucion. curl es para el healthcheck del compose.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmariadb3 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=dependencias /opt/entorno /opt/entorno

RUN useradd --system --create-home --uid 10001 apofyx
WORKDIR /app
COPY --chown=apofyx:apofyx . .

#  La carpeta donde collectstatic deja su trabajo tiene que existir y ser
#  suya: el proceso no corre como root y no podria crearla.
#
#  Y el entrypoint se deja ejecutable y con finales LF aca mismo, en vez de
#  confiar en el clon: Git en Windows no guarda el bit de ejecucion, y una
#  copia de trabajo con CRLF hace que Linux busque un interprete llamado
#  "/bin/sh\r". .gitattributes ya lo impide; esto cubre las copias que se
#  sacaron antes de que existiera.
RUN mkdir -p /app/staticfiles && chown apofyx:apofyx /app/staticfiles \
 && sed -i 's/\r$//' /app/docker-entrada.sh \
 && chmod +x /app/docker-entrada.sh

USER apofyx
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrada.sh"]
#  Tres trabajadores: suficiente para una demostracion y para que una peticion
#  lenta no deje al resto esperando.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
