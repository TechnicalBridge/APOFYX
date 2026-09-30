"""
Una empresa se suma a APOFYX sin que nadie toque la base a mano.

- Sin rubros: APOFYX cobra para cualquier empresa con cobros atrasados, y el
  rubro no cambiaba nada de como se cobra. Se van crm_industry y las columnas
  industry_id de crm_creditor y crm_lead.
- Sin crm_portfoliohandover: era el agregado de cartera que se cargaba a mano.
  La cartera de una empresa es la que entrego, deuda por deuda (app cartera).
- La cuenta de la empresa es un contacto con acceso: crm_creditorcontact suma
  user_id y portal_access.
- v_company_overview se reescribe sobre la cartera real.
- El asistente deja de listar rubros cuando le preguntan para quien sirve.

Todo va envuelto en SiFalta/SiSobra: la misma migracion sirve para una base
creada con el DDL de hoy, con uno anterior, y para la de pruebas.

La clave foranea de user_id a auth_user la agrega esta migracion y no el DDL:
auth_user la crea Django al migrar, despues de que corre el DDL.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import crm.campos
from crm.operaciones import SiFalta, SiSobra

VISTA = """
CREATE OR REPLACE VIEW v_company_overview AS
SELECT
    c.id              AS creditor_id,
    c.trade_name,
    c.legal_name,
    c.tax_id,
    c.status,
    c.client_since,
    COALESCE(cd.debts_in_management, 0) AS debts_in_management,
    COALESCE(cd.average_debt_clp, 0)    AS average_debt_clp,
    cd.last_cut_off,
    (SELECT COUNT(*) FROM crm_campaign cm
      WHERE cm.creditor_id = c.id AND cm.status = 'running') AS running_campaigns
FROM crm_creditor c
LEFT JOIN (
    SELECT d.creditor_id,
           COUNT(*)       AS debts_in_management,
           MAX(b.cut_off) AS last_cut_off,
           ROUND(AVG(CASE WHEN d.currency = 'CLP' THEN t.monto END), 2) AS average_debt_clp
      FROM cartera_debt d
      JOIN cartera_batch b ON b.id = d.last_batch_id
      LEFT JOIN (SELECT debt_id, SUM(amount) AS monto
                   FROM cartera_debtcharge GROUP BY debt_id) t ON t.debt_id = d.id
     WHERE d.status IN ('open', 'repacted', 'disputed')
     GROUP BY d.creditor_id
) cd ON cd.creditor_id = c.id
"""


def vista_y_clave_foranea(apps, schema_editor):
    """Solo en MySQL: en SQLite (las pruebas rapidas) no hay vistas, y Django ya creo la clave."""
    conexion = schema_editor.connection
    if conexion.vendor != "mysql":
        return
    with conexion.cursor() as cursor:
        cursor.execute(VISTA)
        restricciones = conexion.introspection.get_constraints(cursor, "crm_creditorcontact")
        tiene_clave = any(r["foreign_key"] and r["columns"] == ["user_id"] for r in restricciones.values())
        if not tiene_clave:
            cursor.execute(
                "ALTER TABLE crm_creditorcontact ADD CONSTRAINT fk_contact_user "
                "FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE SET NULL"
            )


RESPUESTA = (
    "Atendemos a cualquier empresa que cobre todos los meses y tenga clientes que se atrasan: "
    "arriendos, colegios, gimnasios, clínicas o servicios. El rubro no cambia cómo cobramos. "
    "Su empresa se registra en el portal de empresas, la validamos y desde ahí nos entrega su "
    "cartera, con una planilla o conectando su sistema."
)


def asistente_sin_rubros(apps, schema_editor):
    """El catalogo lo carga el DDL: en una base de pruebas no hay nada que cambiar."""
    Intent = apps.get_model("assistant", "Intent")
    IntentResponse = apps.get_model("assistant", "IntentResponse")
    Intent.objects.filter(slug="rubros_requisitos").update(
        name="Para que empresas sirve", description="A quien atiende APOFYX y como se suma una empresa.")
    IntentResponse.objects.filter(intent__slug="rubros_requisitos", suggested_action="show_industries").update(
        response_text=RESPUESTA, suggested_action="contact_sales")


class Migration(migrations.Migration):

    #  La vista y la clave foranea no se pueden deshacer a medias en MySQL.
    atomic = False

    dependencies = [
        ('crm', '0003_categorias_enum'),
        ('cartera', '0004_categorias_enum'),
        ('assistant', '0003_check_del_motor'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        SiSobra(migrations.RemoveField(model_name='lead', name='industry')),
        SiSobra(migrations.RemoveField(model_name='creditor', name='industry')),
        SiSobra(migrations.DeleteModel(name='Industry')),
        SiSobra(migrations.DeleteModel(name='PortfolioHandover')),
        SiFalta(migrations.AddField(
            model_name='creditorcontact',
            name='user',
            field=models.OneToOneField(
                blank=True, null=True, db_column='user_id',
                on_delete=django.db.models.deletion.SET_NULL, related_name='contacto',
                to=settings.AUTH_USER_MODEL, verbose_name='usuario del portal',
            ),
        )),
        SiFalta(migrations.AddField(
            model_name='creditorcontact',
            name='portal_access',
            field=crm.campos.Categoria(
                blank=True, null=True, max_length=10, verbose_name='acceso al portal',
                choices=[('pending', 'Por aprobar'), ('granted', 'Aprobado'), ('revoked', 'Revocado')],
            ),
        )),
        migrations.RunPython(vista_y_clave_foranea, migrations.RunPython.noop),
        migrations.RunPython(asistente_sin_rubros, migrations.RunPython.noop),
    ]
