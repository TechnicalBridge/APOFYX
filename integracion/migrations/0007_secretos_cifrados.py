"""
Los secretos que APOFYX guarda para leerlos de vuelta, cifrados.

La clave de DataBridge y los dos secretos de los avisos pasan a guardarse con
AES-256-GCM (integracion/cifrado.py). Cifrados son mas largos, asi que las
columnas pasan a VARCHAR(255). Lo que ya estaba guardado en claro se cifra
aqui mismo; volver atras lo deja en claro otra vez.
"""

from django.db import migrations

import integracion.cifrado
from integracion.cifrado import cifrar, descifrar

COLUMNAS = (
    ("integracion_subscription", ("secret",)),
    ("integracion_platformconnection", ("api_key", "events_secret")),
)


def _pasar(schema_editor, convertir):
    #  Con SQL sobre las columnas, y no con el modelo: el campo Cifrado
    #  cifraria al escribir, y volver atras no dejaria nada en claro.
    q = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        for tabla, columnas in COLUMNAS:
            cursor.execute(f"SELECT id, {', '.join(map(q, columnas))} FROM {q(tabla)}")
            for id_, *valores in cursor.fetchall():
                asignar = ", ".join(f"{q(c)} = %s" for c in columnas)
                cursor.execute(f"UPDATE {q(tabla)} SET {asignar} WHERE id = %s",
                               [*(convertir(v) for v in valores), id_])


def cifrar_lo_guardado(apps, schema_editor):
    _pasar(schema_editor, cifrar)


def descifrar_lo_guardado(apps, schema_editor):
    _pasar(schema_editor, descifrar)


class Migration(migrations.Migration):

    dependencies = [
        ('integracion', '0006_platformconnection'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='secret',
            field=integracion.cifrado.Cifrado(max_length=255, verbose_name='secreto'),
        ),
        migrations.AlterField(
            model_name='platformconnection',
            name='api_key',
            field=integracion.cifrado.Cifrado(max_length=255, verbose_name='clave de API'),
        ),
        migrations.AlterField(
            model_name='platformconnection',
            name='events_secret',
            field=integracion.cifrado.Cifrado(blank=True, max_length=255, null=True,
                                              verbose_name='secreto de los avisos'),
        ),
        migrations.RunPython(cifrar_lo_guardado, descifrar_lo_guardado),
    ]
