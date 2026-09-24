#!/bin/sh
# =============================================================================
#  Lo que hay que hacer antes de servir la primera peticion.
# =============================================================================
#  Sin esto, en una maquina recien clonada el contenedor arranca contra una
#  base que tiene las tablas del negocio —las crea sql/AphofyxDB.sql al
#  inicializar MySQL— pero ninguna de las de Django: ni sesiones, ni usuarios.
#  El sitio responde y el panel se cae.
# =============================================================================
set -e

echo "APOFYX: esperando a la base de datos…"
espera=0
until python -c "
import os, sys, MySQLdb
try:
    MySQLdb.connect(host=os.environ.get('DB_HOST', 'db'),
                    port=int(os.environ.get('DB_PORT', 3306)),
                    user=os.environ['DB_USER'],
                    passwd=os.environ['DB_PASSWORD'],
                    db=os.environ.get('DB_NAME', 'apofyx')).close()
except Exception as e:
    print(e, file=sys.stderr); sys.exit(1)
" 2>/dev/null; do
    espera=$((espera + 2))
    if [ "$espera" -gt 120 ]; then
        echo "APOFYX: la base no respondio en dos minutos." >&2
        exit 1
    fi
    sleep 2
done
echo "APOFYX: la base responde."

#  --fake-initial: el esquema del negocio ya lo creo el DDL, asi que Django
#  reconoce esas tablas y las adopta en vez de intentar crearlas. Lo que si
#  crea son las suyas.
python manage.py migrate --fake-initial --noinput

#  Los estaticos van a STATIC_ROOT, donde WhiteNoise los busca. Se hace aqui
#  y no al construir la imagen porque el compose monta el codigo encima y
#  taparia lo que hubiera quedado.
python manage.py collectstatic --noinput --clear >/dev/null
echo "APOFYX: estaticos listos."

#  El superusuario solo si lo piden por variables, y solo si no existe: correr
#  el contenedor dos veces no puede fallar por esto.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
U = get_user_model()
nombre = os.environ['DJANGO_SUPERUSER_USERNAME']
if U.objects.filter(username=nombre).exists():
    print(f'APOFYX: el usuario {nombre} ya estaba.')
else:
    U.objects.create_superuser(nombre,
                               os.environ.get('DJANGO_SUPERUSER_EMAIL', ''),
                               os.environ['DJANGO_SUPERUSER_PASSWORD'])
    print(f'APOFYX: usuario {nombre} creado.')
"
fi

exec "$@"
