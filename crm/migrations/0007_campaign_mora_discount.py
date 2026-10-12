"""
El descuento por tramo de la campana.

Cada campana puede condonar parte de los intereses de mora a quien paga toda la
deuda, segun lo atrasada que esta: {"1-30": 0, "31-90": 50, "91-120": 100}.
Nunca pasa el maximo que autoriza la empresa, y viaja a DataBridge con la
campana (contrato de integracion, §7.1). Vacio: sin descuento.

Envuelta en SiFalta: una base creada con el DDL de hoy ya tiene la columna.
"""

from django.db import migrations, models

from crm.operaciones import SiFalta


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0006_creditor_max_mora_discount'),
    ]

    operations = [
        SiFalta(migrations.AddField(
            model_name='campaign',
            name='mora_discount',
            field=models.JSONField(
                blank=True, null=True, verbose_name='descuento por tramo',
                help_text='El % de los intereses de mora que se condona a quien paga toda la deuda, por tramo: '
                          '{"1-30": 0, "31-90": 50, "91-120": 100}. Vacio: sin descuento.',
            ),
        )),
    ]
