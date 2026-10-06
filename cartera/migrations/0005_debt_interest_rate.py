"""
La tasa de interes que pacto el acreedor.

Algunas deudas generan interes: las que el acreedor pacto asi. Llega en la
cartera (tasa_interes_mensual), APOFYX la guarda y la reenvia a la plataforma
de pagos, que es la que la cobra. Sin tasa, la deuda no genera intereses.

Envuelta en SiFalta: una base creada con el DDL de hoy ya tiene la columna y
el CHECK.
"""

from django.db import migrations, models

from crm.operaciones import SiFalta


class Migration(migrations.Migration):

    dependencies = [
        ('cartera', '0004_categorias_enum'),
    ]

    operations = [
        SiFalta(migrations.AddField(
            model_name='debt',
            name='interest_rate',
            field=models.DecimalField(
                blank=True, null=True, max_digits=5, decimal_places=2, verbose_name='interes mensual',
                help_text='El interes que pacto el acreedor, en porcentaje mensual. Vacio: la deuda no genera intereses.',
            ),
        )),
        SiFalta(migrations.AddConstraint(
            model_name='debt',
            constraint=models.CheckConstraint(
                condition=models.Q(interest_rate__isnull=True) | models.Q(interest_rate__gt=0),
                name='ck_debt_interest_rate',
            ),
        )),
    ]
