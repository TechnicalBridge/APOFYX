"""
La vista v_deuda_features, tambien en las bases que ya existian.

`CREATE OR REPLACE` la hace idempotente: en una base creada con el DDL de hoy la
vuelve a escribir igual, y en una anterior la crea. Va con RunPython y no con
RunSQL porque es SQL de MySQL: en SQLite (las pruebas rapidas) se omite, y las
pruebas de la vista se saltan solas.
"""

from django.db import migrations

SQL = """
CREATE OR REPLACE VIEW v_deuda_features AS
SELECT
    d.id                                              AS deuda_id,
    d.creditor_id                                     AS acreedor_id,
    b.campaign_id                                     AS campana_id,
    COALESCE(c.cargos, 0)                             AS n_cargos,
    COALESCE(c.monto, 0)                              AS monto_total,
    COALESCE(DATEDIFF(b.cut_off, c.vence_primero), 0) AS dias_mora,
    COALESCE(DATEDIFF(b.cut_off, a.client_since), 0)  AS antiguedad_cliente_dias,
    COALESCE(cp.contact_attempts, 0)                  AS intentos_de_contacto,
    COALESCE(ev.eventos, 0)                           AS eventos_recibidos,
    CASE
        WHEN c.vence_primero IS NULL                       THEN 0
        WHEN DATEDIFF(b.cut_off, c.vence_primero) <= 30    THEN 1
        WHEN DATEDIFF(b.cut_off, c.vence_primero) <= 90    THEN 2
        WHEN DATEDIFF(b.cut_off, c.vence_primero) <= 120   THEN 3
        ELSE 4
    END                                               AS tramo_orden,
    (d.status = 'open')                               AS estado_en_gestion,
    (d.status = 'repacted')                           AS estado_en_convenio,
    (d.status = 'paid')                               AS estado_pagada,
    (d.status = 'withdrawn')                          AS estado_retirada,
    (d.status = 'disputed')                           AS estado_disputada,
    (d.currency = 'CLP')                              AS moneda_clp,
    (d.currency = 'UF')                               AS moneda_uf,
    (dr.kind = 'person')                              AS deudor_persona,
    (dr.kind = 'company')                             AS deudor_empresa,
    (dr.email IS NOT NULL AND dr.email <> '')         AS tiene_correo,
    (dr.phone IS NOT NULL AND dr.phone <> '')         AS tiene_telefono,
    (b.source = 'api')                                AS entrega_por_api,
    (b.source = 'file')                               AS entrega_por_archivo,
    COALESCE(JSON_CONTAINS(cp.channels, '"whatsapp"'), 0) AS canal_whatsapp,
    COALESCE(JSON_CONTAINS(cp.channels, '"email"'), 0)    AS canal_correo,
    COALESCE(JSON_CONTAINS(cp.channels, '"sms"'), 0)      AS canal_sms
FROM cartera_debt d
JOIN cartera_batch  b  ON b.id  = d.last_batch_id
JOIN cartera_debtor dr ON dr.id = d.debtor_id
JOIN crm_creditor   a  ON a.id  = d.creditor_id
LEFT JOIN crm_campaign cp ON cp.id = b.campaign_id
LEFT JOIN (
    SELECT debt_id, COUNT(*) AS cargos, SUM(amount) AS monto, MIN(due_date) AS vence_primero
      FROM cartera_debtcharge
     GROUP BY debt_id
) c ON c.debt_id = d.id
LEFT JOIN (
    SELECT debt_id, COUNT(*) AS eventos
      FROM integracion_inboundevent
     WHERE debt_id IS NOT NULL
     GROUP BY debt_id
) ev ON ev.debt_id = d.id
"""


def crear(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute(SQL)


def borrar(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute("DROP VIEW IF EXISTS v_deuda_features")


class Migration(migrations.Migration):

    #  MySQL no revierte un CREATE VIEW, asi que Django no deja ejecutarlo
    #  dentro de una transaccion.
    atomic = False

    dependencies = [
        ("cartera", "0003_debt_repacted"),
        ("integracion", "0003_eventos"),
    ]

    operations = [migrations.RunPython(crear, borrar)]
