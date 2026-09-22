"""
Las categorias pasan de VARCHAR + CHECK a ENUM.

Por dentro MySQL las guarda como un numero de un byte; por fuera se siguen
leyendo y escribiendo como texto (ver crm/campos.py). El CHECK que repetia la
lista se quita: el propio ENUM es la restriccion.
"""

import crm.campos
from django.db import migrations

from crm.operaciones import SiSobra


class Migration(migrations.Migration):

    dependencies = [
        ('cartera', '0003_debt_repacted'),
    ]

    operations = [
        SiSobra(migrations.RemoveConstraint(
            model_name='batch',
            name='ck_batch_source',
        )),
        SiSobra(migrations.RemoveConstraint(
            model_name='batch',
            name='ck_batch_status',
        )),
        SiSobra(migrations.RemoveConstraint(
            model_name='debt',
            name='ck_debt_currency',
        )),
        SiSobra(migrations.RemoveConstraint(
            model_name='debt',
            name='ck_debt_status',
        )),
        SiSobra(migrations.RemoveConstraint(
            model_name='debtor',
            name='ck_debtor_kind',
        )),
        migrations.AlterField(
            model_name='batch',
            name='source',
            field=crm.campos.Categoria(choices=[('api', 'Por API'), ('file', 'Archivo cargado a mano')], default='api', max_length=10, verbose_name='origen'),
        ),
        migrations.AlterField(
            model_name='batch',
            name='status',
            field=crm.campos.Categoria(choices=[('received', 'Recibido'), ('processed', 'Procesado'), ('rejected', 'Rechazado')], default='received', max_length=20, verbose_name='estado'),
        ),
        migrations.AlterField(
            model_name='debt',
            name='currency',
            field=crm.campos.Categoria(choices=[('CLP', 'Pesos'), ('UF', 'UF')], default='CLP', max_length=3, verbose_name='moneda'),
        ),
        migrations.AlterField(
            model_name='debt',
            name='status',
            field=crm.campos.Categoria(choices=[('open', 'En gestion'), ('repacted', 'En convenio de pago'), ('paid', 'Pagada'), ('withdrawn', 'Retirada por el acreedor'), ('disputed', 'Disputada')], default='open', max_length=20, verbose_name='estado'),
        ),
        migrations.AlterField(
            model_name='debtor',
            name='kind',
            field=crm.campos.Categoria(choices=[('person', 'Persona'), ('company', 'Empresa')], default='person', max_length=10, verbose_name='tipo'),
        ),
    ]
