"""
La cadencia de la campana.

La plataforma de pagos ejecuta la campana: manda cada toque el dia que dice la
cadencia, contado desde que la deuda entra. Vacia, la de siempre: 1, 4, 11,
25 y 45.

Envuelta en SiFalta: una base creada con el DDL de hoy ya tiene la columna.
"""

from django.db import migrations, models

from crm.operaciones import SiFalta


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0004_integracion_natural'),
    ]

    operations = [
        SiFalta(migrations.AddField(
            model_name='campaign',
            name='cadence_days',
            field=models.JSONField(
                blank=True, null=True, verbose_name='cadencia (dias)',
                help_text='El dia en que sale cada toque, contado desde que la deuda entra. Vacia: 1, 4, 11, 25, 45.',
            ),
        )),
    ]
