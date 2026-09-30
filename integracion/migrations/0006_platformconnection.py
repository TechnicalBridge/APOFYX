"""
La conexion con la plataforma de pagos, en la base.

Reemplaza a DATABRIDGE_URL, DATABRIDGE_CLAVE y DATABRIDGE_SECRETO_EVENTOS del
.env: el personal conecta APOFYX desde el panel y vale al tiro, sin reiniciar.
Una sola fila: el id es siempre 1, y la base lo obliga.

De paso, "Esperando campaña" con su tilde en el estado del reenvio: el ENUM
de la base guarda el valor y no la etiqueta, asi que no cambia nada en MySQL.
"""

from django.db import migrations, models

import crm.campos
from crm.operaciones import SiFalta


class Migration(migrations.Migration):

    dependencies = [
        ('integracion', '0005_categorias_enum'),
    ]

    operations = [
        SiFalta(migrations.CreateModel(
            name='PlatformConnection',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, primary_key=True, serialize=False)),
                ('url', models.CharField(max_length=300, verbose_name='direccion')),
                ('api_key', models.CharField(max_length=120, verbose_name='clave de API')),
                ('events_secret', models.CharField(blank=True, max_length=120, null=True,
                                                   verbose_name='secreto de los avisos')),
                ('platform_rut', models.CharField(blank=True, max_length=12, null=True,
                                                  verbose_name='RUT de la plataforma')),
                ('platform_name', models.CharField(blank=True, max_length=120, null=True,
                                                   verbose_name='nombre de la plataforma')),
                ('connected_at', models.DateTimeField(blank=True, null=True, verbose_name='conectada')),
                ('last_error', models.CharField(blank=True, max_length=300, null=True,
                                                verbose_name='ultimo error')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='actualizada')),
            ],
            options={
                'verbose_name': 'conexion con la plataforma de pagos',
                'verbose_name_plural': 'conexion con la plataforma de pagos',
                'db_table': 'integracion_platformconnection',
                'constraints': [models.CheckConstraint(condition=models.Q(id=1), name='ck_platformconnection_una')],
            },
        )),
        migrations.AlterField(
            model_name='forward',
            name='status',
            field=crm.campos.Categoria(choices=[('pending', 'Por enviar'), ('waiting', 'Esperando campaña'), ('sent', 'Entregada'), ('failed', 'Fallida')], default='pending', max_length=10, verbose_name='estado'),
        ),
    ]
