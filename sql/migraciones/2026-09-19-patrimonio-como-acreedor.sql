-- =============================================================================
--  2026-09-19 — Patrimonio Inmuebles como empresa acreedora
-- =============================================================================
--  POR QUE EXISTE ESTE ARCHIVO
--  AphofyxDB.sql solo se ejecuta cuando el volumen de Docker esta vacio. Esto
--  lleva a una base ya andando el rubro y el cliente nuevos, que en el script
--  ya quedaron para las instalaciones limpias.
--
--  QUE AGREGA
--  1. El rubro 'Corretaje y arriendos'. Los rubros que ya existian cubren
--     gimnasios, educacion, salud, ISP, edificios y retail; una corredora que
--     administra arriendos no entra en ninguno.
--  2. Patrimonio Inmuebles, el acreedor que entrega su cartera por el contrato
--     de integracion, con su contacto principal.
--
--  COMO SE EJECUTA
--      docker compose exec -T db mysql --default-character-set=utf8mb4 \
--          -u root -p"$MYSQL_ROOT_PASSWORD" apofyx \
--          < sql/migraciones/2026-09-19-patrimonio-como-acreedor.sql
--
--  Es idempotente: correrlo dos veces no duplica nada.
-- =============================================================================

USE apofyx;

INSERT INTO crm_industry (name, slug, description) VALUES
    ('Corretaje y arriendos', 'arriendos',
     'Corredoras que administran arriendos y cobran la renta mes a mes.')
AS nuevo
ON DUPLICATE KEY UPDATE
    name        = nuevo.name,
    description = nuevo.description;

INSERT INTO crm_creditor
    (legal_name, trade_name, tax_id, industry_id,
     status, client_since, commune, region, website) VALUES
    ('Patrimonio Inmuebles SpA', 'Patrimonio Inmuebles', '76418902-7',
     (SELECT id FROM crm_industry WHERE slug = 'arriendos'),
     'active', '2026-09-01', 'Vitacura', 'Metropolitana', 'https://patrimonioinmuebles.cl')
AS nuevo
ON DUPLICATE KEY UPDATE
    legal_name   = nuevo.legal_name,
    trade_name   = nuevo.trade_name,
    industry_id  = nuevo.industry_id,
    status       = nuevo.status,
    client_since = nuevo.client_since,
    commune      = nuevo.commune,
    region       = nuevo.region,
    website      = nuevo.website;

INSERT INTO crm_creditorcontact
    (creditor_id, full_name, job_title, email, phone, is_primary) VALUES
    ((SELECT id FROM crm_creditor WHERE tax_id = '76418902-7'),
     'Elena Vargas Mendoza', 'Directora general',
     'elena.vargas@patrimonioinmuebles.cl', '+56981234401', TRUE)
AS nuevo
ON DUPLICATE KEY UPDATE
    full_name  = nuevo.full_name,
    job_title  = nuevo.job_title,
    phone      = nuevo.phone,
    is_primary = nuevo.is_primary;

SELECT id, trade_name, tax_id, status FROM crm_creditor ORDER BY id;
