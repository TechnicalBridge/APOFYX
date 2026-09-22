"""
Leer el DDL como texto, para poder compararlo con los modelos.

POR QUE HACE FALTA
El esquema real lo crea sql/AphofyxDB.sql, pero Django arma la base de PRUEBAS
desde las migraciones. Las migraciones de las tablas antiguas no llevan ningun
CHECK, asi que una prueba puede guardar un valor que el DDL prohibe, pasar en
verde y reventar en produccion con el error 3819. Paso de verdad con 'churned'
contra 'terminated'.

Estas funciones permiten escribir esa prueba sin base de datos: se lee el .sql
y se compara con lo que los modelos declaran.
"""

import re

from django.conf import settings


def ddl():
    return (settings.BASE_DIR / "sql" / "AphofyxDB.sql").read_text(encoding="utf-8")


def clausula_check(nombre, texto=None):
    """
    El cuerpo del CHECK que se llama `nombre`, tal como esta escrito.

    Cuenta parentesis en vez de cortar por salto de linea: en el DDL hay CHECK
    de una sola linea y otros de varias, y cortar por formato hacia que un
    CHECK se comiera los valores del que venia despues.
    """
    texto = ddl() if texto is None else texto
    inicio = texto.find(f"CONSTRAINT {nombre} CHECK (")
    if inicio == -1:
        return None
    desde = texto.index("(", inicio)
    profundidad = 0
    for posicion in range(desde, len(texto)):
        if texto[posicion] == "(":
            profundidad += 1
        elif texto[posicion] == ")":
            profundidad -= 1
            if profundidad == 0:
                return texto[desde + 1:posicion]
    return None


def valores_del_check(nombre, texto=None):
    """Los literales de un CHECK de lista: {'onboarding', 'active', ...}."""
    clausula = clausula_check(nombre, texto)
    return set(re.findall(r"'([^']+)'", clausula)) if clausula else None
