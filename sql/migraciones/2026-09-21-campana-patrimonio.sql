-- =============================================================================
--  2026-09-21 — La campana que recibe la cartera de Patrimonio
-- =============================================================================
--  POR QUE EXISTE ESTE ARCHIVO
--  Para pasarle una cartera a DataBridge, APOFYX tiene que decirle a que
--  campana va. Patrimonio no tenia ninguna. Esta es la unica en curso de ese
--  acreedor, asi que el reenvio la asigna sin que nadie tenga que hacerlo a
--  mano.
--
--  La tabla de la bandeja de salida (integracion_forward) NO se crea aqui: la
--  crea `python manage.py migrate`, porque nacio en los modelos de Django.
--
--  COMO SE EJECUTA
--      docker compose exec -T db mysql --default-character-set=utf8mb4 \
--          -u root -p"$MYSQL_ROOT_PASSWORD" apofyx \
--          < sql/migraciones/2026-09-21-campana-patrimonio.sql
--
--  Es idempotente: correrlo dos veces no duplica nada.
-- =============================================================================

USE apofyx;

INSERT INTO crm_campaign
    (creditor_id, name, starts_on, ends_on, status, channels, contact_attempts) VALUES
    ((SELECT id FROM crm_creditor WHERE tax_id = '76418902-7'),
     'Patrimonio - Arriendos - Septiembre 2026', '2026-09-19', NULL, 'running',
     JSON_ARRAY('whatsapp', 'email'), 5)
AS nuevo
ON DUPLICATE KEY UPDATE
    starts_on        = nuevo.starts_on,
    ends_on          = nuevo.ends_on,
    status           = nuevo.status,
    channels         = nuevo.channels,
    contact_attempts = nuevo.contact_attempts;

SELECT c.id, c.name, c.status, c.channels
  FROM crm_campaign c
  JOIN crm_creditor a ON a.id = c.creditor_id
 WHERE a.tax_id = '76418902-7';
