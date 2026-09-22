"""
Las categorias pasan de VARCHAR + CHECK a ENUM.

Por dentro MySQL las guarda como un numero de un byte; por fuera se siguen
leyendo y escribiendo como texto (ver crm/campos.py). El CHECK que repetia la
lista se quita: el propio ENUM es la restriccion.
"""

import crm.campos
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0002_embudo_con_pagos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='campaign',
            name='status',
            field=crm.campos.Categoria(choices=[('draft', 'Borrador'), ('running', 'En curso'), ('paused', 'Pausada'), ('finished', 'Finalizada')], default='draft', max_length=20, verbose_name='estado'),
        ),
        migrations.AlterField(
            model_name='creditor',
            name='status',
            field=crm.campos.Categoria(choices=[('onboarding', 'En incorporacion'), ('active', 'Activa'), ('paused', 'Pausada'), ('churned', 'Dada de baja')], default='onboarding', max_length=20, verbose_name='estado'),
        ),
        migrations.AlterField(
            model_name='lead',
            name='current_collection_method',
            field=crm.campos.Categoria(blank=True, choices=[('nadie', 'Hoy nadie la gestiona'), ('llamadas', 'Llamamos por telefono'), ('mensajes', 'Enviamos correos o mensajes a mano'), ('externo', 'Una empresa de cobranza externa'), ('mixto', 'Una mezcla de varias')], max_length=20, null=True, verbose_name='como cobran hoy'),
        ),
        migrations.AlterField(
            model_name='lead',
            name='source',
            field=crm.campos.Categoria(choices=[('form', 'Formulario'), ('assistant', 'Asistente')], default='form', max_length=20, verbose_name='origen'),
        ),
        migrations.AlterField(
            model_name='lead',
            name='status',
            field=crm.campos.Categoria(choices=[('new', 'Nuevo'), ('contacted', 'Contactado'), ('qualified', 'Calificado'), ('converted', 'Convertido'), ('discarded', 'Descartado')], default='new', max_length=20, verbose_name='estado'),
        ),
        migrations.AlterField(
            model_name='portfoliohandover',
            name='overdue_bracket',
            field=crm.campos.Categoria(choices=[('1-30', '1 a 30 dias'), ('31-90', '31 a 90 dias'), ('91-120', '91 a 120 dias')], max_length=20, verbose_name='tramo de mora'),
        ),
    ]
