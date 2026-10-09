"""
El descuento maximo que autoriza la empresa.

El descuento por pronto pago sale de la plata de la empresa acreedora: ella
fija cuanto de los intereses de mora autoriza condonar, y APOFYX se lo manda a
DataBridge en el mandato (contrato de integracion, §7.1). Vacio es 0: ninguna
campana puede ofrecer descuento.

Envuelta en SiFalta: una base creada con el DDL de hoy ya tiene la columna y
el CHECK.
"""

import django.core.validators
from django.db import migrations, models

from crm.operaciones import SiFalta


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0005_campaign_cadence_days'),
    ]

    operations = [
        SiFalta(migrations.AddField(
            model_name='creditor',
            name='max_mora_discount',
            field=models.DecimalField(
                blank=True, null=True, max_digits=5, decimal_places=2,
                validators=[
                    django.core.validators.MinValueValidator(0, 'El descuento es un porcentaje de 0 a 100.'),
                    django.core.validators.MaxValueValidator(100, 'El descuento es un porcentaje de 0 a 100.'),
                ],
                verbose_name='descuento maximo sobre la mora (%)',
                help_text='El % de los intereses de mora que la empresa autoriza condonar a quien paga toda su '
                          'deuda. Vacio: ninguno.',
            ),
        )),
        SiFalta(migrations.AddConstraint(
            model_name='creditor',
            constraint=models.CheckConstraint(
                condition=models.Q(max_mora_discount__isnull=True)
                | models.Q(max_mora_discount__gte=0, max_mora_discount__lte=100),
                name='ck_creditor_mora_discount',
            ),
        )),
    ]
