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

Solo acepta operaciones que crean algo que se puede buscar en la base: una
tabla, una columna, una restriccion o un indice.
"""

from django.db import migrations
from django.db.migrations.operations.base import Operation


class SiFalta(Operation):
    reversible = True
    reduces_to_sql = False

    ACEPTADAS = (migrations.CreateModel, migrations.AddField, migrations.AddConstraint, migrations.AddIndex)

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
        if isinstance(op, migrations.AddField):
            columna = estado.apps.get_model(app_label, op.model_name)._meta.get_field(op.name).column
            with schema_editor.connection.cursor() as cursor:
                return any(c.name == columna for c in introspeccion.get_table_description(cursor, tabla))
        nombre = op.constraint.name if isinstance(op, migrations.AddConstraint) else op.index.name
        with schema_editor.connection.cursor() as cursor:
            return nombre in introspeccion.get_constraints(cursor, tabla)


class SiSobra(Operation):
    """
    El reverso de {@link SiFalta}: quita algo solo si esta.

    Cuando algo desaparece del DDL —el CHECK de una categoria que paso a ser
    ENUM, una columna o una tabla que ya no se usan— la migracion que lo quita
    se cae en una base creada con el DDL nuevo, porque ahi nunca existio.
    """

    reversible = True
    reduces_to_sql = False

    ACEPTADAS = (migrations.RemoveConstraint, migrations.RemoveIndex, migrations.RemoveField,
                 migrations.DeleteModel)

    def __init__(self, operacion):
        if not isinstance(operacion, self.ACEPTADAS):
            raise TypeError(f"SiSobra no sabe si existe lo que quita {type(operacion).__name__}")
        self.operacion = operacion

    def deconstruct(self):
        return (f"{__name__}.{self.__class__.__qualname__}", [self.operacion], {})

    def state_forwards(self, app_label, state):
        self.operacion.state_forwards(app_label, state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if self._existe(app_label, schema_editor, from_state):
            self.operacion.database_forwards(app_label, schema_editor, from_state, to_state)

    def _existe(self, app_label, schema_editor, estado):
        op = self.operacion
        introspeccion = schema_editor.connection.introspection
        if isinstance(op, migrations.DeleteModel):
            return estado.apps.get_model(app_label, op.name)._meta.db_table in introspeccion.table_names()

        modelo = estado.apps.get_model(app_label, op.model_name)
        tabla = modelo._meta.db_table
        if tabla not in introspeccion.table_names():
            return False
        with schema_editor.connection.cursor() as cursor:
            if isinstance(op, migrations.RemoveField):
                columna = modelo._meta.get_field(op.name).column
                return any(c.name == columna for c in introspeccion.get_table_description(cursor, tabla))
            return op.name in introspeccion.get_constraints(cursor, tabla)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        self.operacion.database_backwards(app_label, schema_editor, from_state, to_state)

    def describe(self):
        return f"{self.operacion.describe()} (si sobra)"

    @property
    def migration_name_fragment(self):
        return self.operacion.migration_name_fragment


class SiLaTablaExiste(Operation):
    """
    Aplica una operacion sobre una tabla solo si la tabla existe.

    Para las migraciones antiguas que tocan una tabla que el DDL de hoy ya no
    crea —crm_portfoliohandover, que se fue con la cartera real—: en una base
    nacida del DDL nuevo no hay nada que alterar. En el estado de Django se
    aplica siempre, asi los modelos y las migraciones siguen calzando.
    """

    reversible = True
    reduces_to_sql = False

    def __init__(self, operacion):
        self.operacion = operacion

    def deconstruct(self):
        return (f"{__name__}.{self.__class__.__qualname__}", [self.operacion], {})

    def state_forwards(self, app_label, state):
        self.operacion.state_forwards(app_label, state)

    def _existe(self, app_label, schema_editor, estado):
        tabla = estado.apps.get_model(app_label, self.operacion.model_name)._meta.db_table
        return tabla in schema_editor.connection.introspection.table_names()

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if self._existe(app_label, schema_editor, from_state):
            self.operacion.database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if self._existe(app_label, schema_editor, to_state):
            self.operacion.database_backwards(app_label, schema_editor, from_state, to_state)

    def describe(self):
        return f"{self.operacion.describe()} (si la tabla existe)"

    @property
    def migration_name_fragment(self):
        return self.operacion.migration_name_fragment
