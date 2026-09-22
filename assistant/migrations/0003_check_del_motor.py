"""
El CHECK del motor de respuesta deja de repetir la lista de valores.

Desde que `answer_engine` es un ENUM, los valores posibles los declara la
columna. Lo que esta regla dice es otra cosa, y por eso se queda: el motor de
respuesta lo tiene el asistente y nunca el visitante.

El CHECK no vive en el modelo —las tablas del asistente declaran sus
restricciones en el DDL—, asi que Django no lo cambia solo y hay que pedirlo
aqui.
"""

from django.db import migrations

VIEJO = "ck_message_engine"
NUEVO = """
    ALTER TABLE assistant_message
        ADD CONSTRAINT ck_message_engine CHECK (
            (speaker = 'visitor'   AND answer_engine IS NULL)
            OR
            (speaker = 'assistant' AND answer_engine IS NOT NULL)
        )
"""


def existe(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        return VIEJO in schema_editor.connection.introspection.get_constraints(
            cursor, "assistant_message")


def alinear(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    if existe(schema_editor):
        schema_editor.execute(f"ALTER TABLE assistant_message DROP CHECK {VIEJO}")
    schema_editor.execute(NUEVO)


def volver(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    if existe(schema_editor):
        schema_editor.execute(f"ALTER TABLE assistant_message DROP CHECK {VIEJO}")
    schema_editor.execute("""
        ALTER TABLE assistant_message
            ADD CONSTRAINT ck_message_engine CHECK (
                (speaker = 'visitor'   AND answer_engine IS NULL)
                OR
                (speaker = 'assistant' AND answer_engine IN ('rules', 'llm', 'fallback'))
            )
    """)


class Migration(migrations.Migration):

    #  MySQL no revierte un ALTER, asi que no puede ir en una transaccion.
    atomic = False

    dependencies = [("assistant", "0002_categorias_enum")]

    operations = [migrations.RunPython(alinear, volver)]
