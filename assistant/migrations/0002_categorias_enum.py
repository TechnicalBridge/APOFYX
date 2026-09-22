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
        ('assistant', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='conversation',
            name='inferred_audience',
            field=crm.campos.Categoria(blank=True, choices=[('prospect', 'Empresa interesada'), ('debtor', 'Persona con deuda'), ('general', 'General')], max_length=20, null=True, verbose_name='publico inferido'),
        ),
        migrations.AlterField(
            model_name='intent',
            name='audience',
            field=crm.campos.Categoria(choices=[('prospect', 'Empresa interesada'), ('debtor', 'Persona con deuda'), ('general', 'General')], default='general', max_length=20, verbose_name='publico'),
        ),
        migrations.AlterField(
            model_name='message',
            name='answer_engine',
            field=crm.campos.Categoria(blank=True, choices=[('rules', 'Catalogo de reglas'), ('llm', 'Modelo de lenguaje'), ('fallback', 'Respuesta de respaldo')], max_length=10, null=True, verbose_name='motor que respondio'),
        ),
        migrations.AlterField(
            model_name='message',
            name='speaker',
            field=crm.campos.Categoria(choices=[('visitor', 'Visitante'), ('assistant', 'Asistente')], max_length=10, verbose_name='quien habla'),
        ),
    ]
