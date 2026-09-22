"""
Operaciones de migracion para un esquema que nace en SQL.

EL PROBLEMA
En APOFYX la base se crea con sql/AphofyxDB.sql y Django la adopta con
`migrate --fake-initial`. Esa bandera solo reconoce las migraciones INICIALES.
Una migracion posterior —una tabla nueva, un CHECK nuevo— se ejecuta siempre,
y en una base creada con el DDL de hoy eso ya existe: MySQL responde "la tabla
ya existe" o "restriccion duplicada" y `migrate` se detiene a mitad de camino.

LA SALIDA
`SiFalta` envuelve una operacion normal. En el estado de Django la aplica
siempre, asi que los modelos y las migraciones siguen calzando. En la base la
ejecuta solo si lo que crea todavia no esta. La misma migracion sirve para las
tres bases que existen:

    creada con el DDL de hoy       ya lo tiene  -> no toca nada
    creada con un DDL anterior     le falta     -> lo crea
    la de pruebas (solo migracion) le falta     -> lo crea

Solo acepta operaciones que crean algo con nombre propio, porque son las
unicas en que "ya existe" se puede responder mirando la base.
"""

from django.db import migrations
from django.db.migrations.operations.base import Operation


class SiFalta(Operation):
    reversible = True
    reduces_to_sql = False

    ACEPTADAS = (migrations.CreateModel, migrations.AddConstraint, migrations.AddIndex)

    def __init__(self, operacion):
        if not isinstance(operacion, self.ACEPTADAS):
            raise TypeError(f"SiFalta no sabe si ya existe lo que crea {type(operacion).__name__}")
        self.operacion = operacion

    def deconstruct(self):
        return (f"{__name__}.{self.__class__.__qualname__}", [self.operacion], {})

    def state_forwards(self, app_label, state):
        self.operacion.state_forwards(app_label, state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if not self._ya_existe(app_label, schema_editor, to_state):
            self.operacion.database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        self.operacion.database_backwards(app_label, schema_editor, from_state, to_state)

    def describe(self):
        return f"{self.operacion.describe()} (si falta)"

    @property
    def migration_name_fragment(self):
        return self.operacion.migration_name_fragment

    def _ya_existe(self, app_label, schema_editor, estado):
        op = self.operacion
        introspeccion = schema_editor.connection.introspection

        if isinstance(op, migrations.CreateModel):
            tabla = estado.apps.get_model(app_label, op.name)._meta.db_table
            return tabla in introspeccion.table_names()

        tabla = estado.apps.get_model(app_label, op.model_name)._meta.db_table
        nombre = op.constraint.name if isinstance(op, migrations.AddConstraint) else op.index.name
        with schema_editor.connection.cursor() as cursor:
            return nombre in introspeccion.get_constraints(cursor, tabla)
