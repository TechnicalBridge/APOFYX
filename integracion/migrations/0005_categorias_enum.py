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
        ('integracion', '0004_vista_features'),
    ]

    operations = [
        SiSobra(migrations.RemoveConstraint(
            model_name='forward',
            name='ck_forward_status',
        )),
        SiSobra(migrations.RemoveConstraint(
            model_name='outboundevent',
            name='ck_outboundevent_status',
        )),
        migrations.AlterField(
            model_name='forward',
            name='status',
            field=crm.campos.Categoria(choices=[('pending', 'Por enviar'), ('waiting', 'Esperando campana'), ('sent', 'Entregada'), ('failed', 'Fallida')], default='pending', max_length=10, verbose_name='estado'),
        ),
        migrations.AlterField(
            model_name='outboundevent',
            name='status',
            field=crm.campos.Categoria(choices=[('pending', 'Por enviar'), ('delivered', 'Entregado'), ('failed', 'Fallido')], default='pending', max_length=10, verbose_name='estado'),
        ),
    ]
