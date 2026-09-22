#!/usr/bin/env bash
# =============================================================================
#  Vuelve a crear la base desde sql/AphofyxDB.sql, conservando los datos.
# =============================================================================
#  Para que sirve
#  --------------
#  El DDL es la fuente del esquema y los modelos son su espejo. Una base que
#  lleva meses en uso, en cambio, va guardando lo que le hicieron las
#  migraciones por el camino: indices con el nombre que inventa Django
#  ('cartera_debt_debtor_id_eaeb0d6d_fk_...'), CHECK de categorias que el DDL
#  ya no declara desde que son ENUM, columnas sin su DEFAULT. Nada de eso
#  rompe la aplicacion —Django escribe todas las columnas siempre— pero la
#  base deja de ser la que describe el repositorio, y eso se paga el dia que
#  alguien agrega un valor al ENUM y su base lo rechaza por un CHECK viejo.
#
#  Este script borra la base y la vuelve a crear desde el archivo, devolviendo
#  despues los datos que habia.
#
#  Uso
#  ---
#      bash sql/rehacer.sh            # rehace y devuelve los datos
#      bash sql/rehacer.sh --vacia    # rehace y deja solo lo que siembra el DDL
#
#  Antes conviene apagar lo que este conectado (runserver, el demo, Workbench).
#  El respaldo completo queda en sql/.respaldo-<fecha>.sql por si algo falla.
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."
BASE="${DB_NAME:-apofyx}"
CLAVE="${MYSQL_ROOT_PASSWORD:-rootpass}"
MYSQL="docker compose exec -T db mysql -uroot -p$CLAVE --default-character-set=utf8mb4"
VOLCAR="docker compose exec -T db mysqldump -uroot -p$CLAVE --default-character-set=utf8mb4"

#  MySQL avisa en cada llamada que la clave va en la linea de comandos. Ese
#  aviso se calla; cualquier otra cosa que diga se muestra, porque un error
#  que nadie ve es peor que no correr el script.
callar() { grep -v 'Using a password on the command line' >&2 || true; }
PY=".venv/Scripts/python.exe"; [ -x "$PY" ] || PY=".venv/bin/python"
RESPALDO="sql/.respaldo-$(date +%Y%m%d-%H%M%S).sql"
DATOS="sql/.datos-$$.sql"
trap 'rm -f "$DATOS"' EXIT

#  Las vistas no llevan datos propios y django_migrations lo vuelve a escribir
#  'migrate', asi que ninguna de las dos entra en el volcado de datos.
SALTAR=""
for t in django_migrations v_assistant_coverage v_campaign_funnel \
         v_company_overview v_deuda_features; do
    SALTAR="$SALTAR --ignore-table=$BASE.$t"
done

echo "1/5  respaldo completo en $RESPALDO"
$VOLCAR --single-transaction --routines --events "$BASE" > "$RESPALDO" 2> >(callar)

if [ "${1:-}" != "--vacia" ]; then
    echo "2/5  guardando los datos"
    #  --complete-insert nombra cada columna: el DDL las ordena distinto que
    #  Django, y sin los nombres los valores caerian corridos de columna.
    $VOLCAR --no-create-info --complete-insert --replace --skip-extended-insert \
            --single-transaction $SALTAR "$BASE" > "$DATOS" 2> >(callar)
    echo "     $(grep -c '^REPLACE INTO' "$DATOS") filas"
else
    echo "2/5  sin guardar datos (--vacia)"
    : > "$DATOS"
fi

echo "3/5  borrando y creando desde sql/AphofyxDB.sql"
echo "DROP DATABASE IF EXISTS \`$BASE\`;" | $MYSQL 2> >(callar)
$MYSQL < sql/AphofyxDB.sql > /dev/null 2> >(callar)

echo "4/5  Django adopta la base"
"$PY" manage.py migrate --fake-initial 2>&1 | grep -E 'FAKED|OK|Error' | tail -5

echo "5/5  devolviendo los datos"
#  Las claves foraneas se apagan durante la carga porque el volcado va en
#  orden alfabetico y no en orden de dependencias.
{ echo "SET FOREIGN_KEY_CHECKS=0;"; echo "USE \`$BASE\`;"; cat "$DATOS";
  echo "SET FOREIGN_KEY_CHECKS=1;"; } | $MYSQL 2> >(callar)

#  mysql se detiene en el primer error de la carga. Sin este recuento, una
#  carga que quedo por la mitad se veria igual que una completa.
ESCRITAS=$(grep -c '^REPLACE INTO' "$DATOS" || true)
LEIDAS=$(echo "SELECT COUNT(*) FROM cartera_debt;" | $MYSQL -N "$BASE" 2> >(callar))
echo "     $ESCRITAS filas devueltas; $LEIDAS deudas en la base"

echo
echo "Listo. La base coincide con sql/AphofyxDB.sql."
echo "Si algo quedo mal:  docker compose exec -T db mysql -uroot -p$CLAVE $BASE < $RESPALDO"
