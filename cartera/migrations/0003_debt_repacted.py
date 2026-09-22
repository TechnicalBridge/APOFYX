"""
La deuda pasa a aceptar el estado 'repacted' (en convenio de pago).

El CHECK que enumeraba los estados se quita para volver a escribirlo con el
valor nuevo. En una base creada desde el DDL de hoy ese CHECK ya no existe
—la columna es un ENUM y el tipo es la restriccion—, asi que quitarlo tiene
que ser opcional: de eso se encarga SiSobra. Lo que este archivo agrega lo
vuelve a quitar 0004_categorias_enum; se conserva porque las bases que ya
corrieron esta migracion no pueden saltarsela.
"""

from django.db import migrations, models

from crm.operaciones import SiSobra


class Migration(migrations.Migration):

    dependencies = [
        ('cartera', '0002_debtor_ck_debtor_tax_id'),
        ('crm', '0001_initial'),
    ]

    operations = [
        SiSobra(migrations.RemoveConstraint(
            model_name='debt',
            name='ck_debt_status',
        )),
        migrations.AlterField(
            model_name='debt',
            name='status',
            field=models.CharField(choices=[('open', 'En gestion'), ('repacted', 'En convenio de pago'), ('paid', 'Pagada'), ('withdrawn', 'Retirada por el acreedor'), ('disputed', 'Disputada')], default='open', max_length=20, verbose_name='estado'),
        ),
        migrations.AddConstraint(
            model_name='debt',
            constraint=models.CheckConstraint(condition=models.Q(('status__in', ['open', 'repacted', 'paid', 'withdrawn', 'disputed'])), name='ck_debt_status'),
        ),
    ]
