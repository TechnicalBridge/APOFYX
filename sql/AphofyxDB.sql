-- =============================================================================
--  AphofyxDB.sql  —  APOFYX · base de datos completa (DDL + DML)
-- =============================================================================
--  Motor    : MySQL 8.4 (InnoDB)
--  Charset  : utf8mb4 / utf8mb4_0900_ai_ci
--  Fecha    : 15-09-2026
--  Verificado ejecutandose sobre MySQL 8.4.11 limpio.
--
--  COMO SE EJECUTA
--      mysql -u root -p --default-character-set=utf8mb4 < AphofyxDB.sql
--  o desde MySQL Workbench:  File > Open SQL Script > Ejecutar.
--
--  RE-EJECUCION
--  Los INSERT son idempotentes: se pueden repetir sin duplicar nada.
--  Los CREATE TABLE no lo son: si las tablas ya existen el script se detiene
--  con "ERROR 1050 ... Table already exists". Es deliberado — asi un cambio
--  de esquema no pasa inadvertido en silencio.
--  Para reconstruir desde cero: descomentar el BLOQUE DE REINICIO de mas
--  abajo y volver a ejecutar el archivo completo.
--
--  CONTENIDO
--      PARTE 1 — DDL   base de datos, 21 tablas, restricciones, indices, vistas
--      PARTE 2 — DML   datos de referencia (rubros)
--      PARTE 3 — DML   datos de demostracion (5 clientes y sus campanas)
--      PARTE 4 — DML   catalogo del asistente (intenciones, patrones, respuestas)
--      PARTE 5 —       permisos para las pruebas
--      PARTE 6 —       verificacion final
--
--  CONVENCIONES
--  Los nombres siguen las convenciones de Django para que los modelos que se
--  escriban despues produzcan este mismo esquema:
--      · tabla            -> <app>_<modelo en minusculas>   (crm_creditor)
--      · clave primaria   -> id BIGINT AUTO_INCREMENT
--      · clave foranea    -> <campo>_id
--      · fechas           -> DATETIME(6), precision de microsegundos
--
--  IDIOMA
--  Identificadores en ingles, datos en espanol. En los campos con opciones eso
--  se traduce en que los estados internos del sistema van en ingles (status,
--  source, answer_engine, speaker, audience) y el unico campo que guarda lo que
--  una persona declara de su propia operacion va en espanol
--  (crm_lead.current_collection_method). No es un renombrado a medias.
--
--  CUATRO APPS
--      crm         -> clientes B2B de APOFYX, carteras y campanas
--      assistant   -> catalogo de intenciones y conversaciones del chatbot
--      cartera     -> la cartera morosa que entregan los acreedores
--      integracion -> el borde por donde entra esa cartera
--
--  ALCANCE — ver docs/APOFYX.md §2.2 y §13
--  APOFYX SI guarda deudores y deudas: es una empresa de cobranza y sin la
--  cartera no tiene nada que trabajar. Lo que NO existe aca es ninguna tabla
--  de pago ni de transaccion. El dinero lo mueve DataBridge; a APOFYX le
--  llega el aviso y cambia el estado de la deuda.
--
--  TABLAS DE DJANGO
--  Este script NO crea auth_user, django_session ni django_migrations.
--  Esas las genera "python manage.py migrate" y no deben escribirse a mano.
-- =============================================================================


-- =============================================================================
--  PARTE 1 — DDL
-- =============================================================================
-- -----------------------------------------------------------------------------
--  Base de datos
-- -----------------------------------------------------------------------------
--  IMPORTANTE: fuerza la codificacion de ESTA conexion.
--  Sin esta linea, algunos clientes interpretan el archivo como latin1 y los
--  acentos quedan rotos: "Clinica" se guarda como "ClÃ­nica". Le pasa al
--  cliente que usa la imagen de Docker para cargar los scripts de
--  inicializacion, que no recibe --default-character-set.
--  Ponerlo aqui adentro lo hace independiente de como se invoque el script.
SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS apofyx
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE apofyx;


-- -----------------------------------------------------------------------------
--  Reinicio para desarrollo — DESCOMENTAR SOLO SI QUIERES BORRAR TODO
--  El orden es inverso al de creacion para respetar las claves foraneas.
-- -----------------------------------------------------------------------------
-- DROP TABLE IF EXISTS integracion_outboundevent;
-- DROP TABLE IF EXISTS integracion_inboundevent;
-- DROP TABLE IF EXISTS integracion_subscription;
-- DROP TABLE IF EXISTS integracion_forward;
-- DROP TABLE IF EXISTS integracion_apikey;
-- DROP TABLE IF EXISTS cartera_debtcharge;
-- DROP TABLE IF EXISTS cartera_debt;
-- DROP TABLE IF EXISTS cartera_debtor;
-- DROP TABLE IF EXISTS cartera_batch;
-- DROP TABLE IF EXISTS crm_lead;
-- DROP TABLE IF EXISTS assistant_message;
-- DROP TABLE IF EXISTS assistant_conversation;
-- DROP TABLE IF EXISTS assistant_intentresponse;
-- DROP TABLE IF EXISTS assistant_intentpattern;
-- DROP TABLE IF EXISTS assistant_intent;
-- DROP TABLE IF EXISTS crm_campaignfunnelsnapshot;
-- DROP TABLE IF EXISTS crm_campaign;
-- DROP TABLE IF EXISTS crm_portfoliohandover;
-- DROP TABLE IF EXISTS crm_creditorcontact;
-- DROP TABLE IF EXISTS crm_creditor;
-- DROP TABLE IF EXISTS crm_industry;


-- =============================================================================
--  A. TABLAS DE REFERENCIA
-- =============================================================================

-- -----------------------------------------------------------------------------
--  crm_industry — rubros atendidos (gimnasios, educacion, salud, ISP, ...)
-- -----------------------------------------------------------------------------
CREATE TABLE crm_industry (
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    name          VARCHAR(80)  NOT NULL,
    slug          VARCHAR(80)  NOT NULL,
    description   VARCHAR(255)     NULL,
    is_active     BOOL         NOT NULL DEFAULT TRUE,
    created_at    DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_industry        PRIMARY KEY (id),
    CONSTRAINT uq_industry_name   UNIQUE (name),
    CONSTRAINT uq_industry_slug   UNIQUE (slug)
) ENGINE=InnoDB;


-- =============================================================================
--  B. CLIENTES B2B
-- =============================================================================

-- -----------------------------------------------------------------------------
--  crm_creditor — las empresas acreedoras que contratan a APOFYX.
--  Es lo unico que administra el panel (docs §12.2).
--
--  tax_id : RUT normalizado SIN puntos y CON guion -> '76543210-3'
--           Se guarda normalizado para que el UNIQUE funcione de verdad;
--           el formateo con puntos es responsabilidad de la presentacion.
--           ck_creditor_tax_id obliga ese formato en la base, porque el RUT es
--           la llave con la que esta empresa se identifica fuera de APOFYX.
--           El digito verificador NO se valida aca: el modulo 11 es aritmetica
--           y un CHECK con REGEXP no lo alcanza. Eso lo valida el formulario.
-- -----------------------------------------------------------------------------
CREATE TABLE crm_creditor (
    id            BIGINT        NOT NULL AUTO_INCREMENT,
    legal_name    VARCHAR(160)  NOT NULL,
    trade_name    VARCHAR(120)  NOT NULL,
    tax_id        VARCHAR(12)   NOT NULL,
    industry_id   BIGINT        NOT NULL,
    status        VARCHAR(20)   NOT NULL DEFAULT 'onboarding',
    client_since  DATE              NULL,
    commune       VARCHAR(80)       NULL,
    region        VARCHAR(80)       NULL,
    website       VARCHAR(200)      NULL,
    internal_notes         TEXT              NULL,
    created_at    DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at    DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                         ON UPDATE CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_creditor         PRIMARY KEY (id),
    CONSTRAINT uq_creditor_tax_id  UNIQUE (tax_id),

    CONSTRAINT fk_creditor_industry FOREIGN KEY (industry_id)
        REFERENCES crm_industry (id) ON DELETE RESTRICT,

    CONSTRAINT ck_creditor_status CHECK (
        status IN ('onboarding', 'active', 'paused', 'churned')
    ),
    CONSTRAINT ck_creditor_tax_id CHECK (
        tax_id REGEXP '^[0-9]{7,8}-[0-9K]$'
    ),

    INDEX ix_creditor_status   (status),
    INDEX ix_creditor_industry (industry_id),
    INDEX ix_creditor_trade    (trade_name)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
--  crm_creditorcontact — personas de contacto en la empresa cliente.
--
--  primary_slot es una columna generada que vale 1 cuando el contacto es el
--  principal y NULL cuando no lo es. Como MySQL ignora los NULL en un indice
--  UNIQUE, esto fuerza "a lo mas UN contacto principal por empresa" a nivel
--  de base de datos, sin necesidad de un trigger.
-- -----------------------------------------------------------------------------
CREATE TABLE crm_creditorcontact (
    id            BIGINT        NOT NULL AUTO_INCREMENT,
    creditor_id    BIGINT        NOT NULL,
    full_name     VARCHAR(120)  NOT NULL,
    job_title     VARCHAR(80)       NULL,
    email         VARCHAR(254)  NOT NULL,
    phone         VARCHAR(20)       NULL,
    is_primary    BOOL          NOT NULL DEFAULT FALSE,
    created_at    DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at    DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                         ON UPDATE CURRENT_TIMESTAMP(6),

    primary_slot  TINYINT AS (IF(is_primary, 1, NULL)) STORED,

    CONSTRAINT pk_contact           PRIMARY KEY (id),
    CONSTRAINT uq_contact_email     UNIQUE (creditor_id, email),
    CONSTRAINT uq_contact_primary   UNIQUE (creditor_id, primary_slot),

    CONSTRAINT fk_contact_creditor FOREIGN KEY (creditor_id)
        REFERENCES crm_creditor (id) ON DELETE CASCADE,

    INDEX ix_contact_creditor (creditor_id)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
--  crm_portfoliohandover — volumen de cartera que la empresa entrega a gestion,
--  por periodo mensual y tramo de mora.
--
--  OJO: aca NO hay deudores ni deudas individuales. Solo el agregado comercial
--  (cuantos registros y de que ticket promedio). Ver docs §2.2.
--
--  period_month : se guarda siempre como el dia 1 del mes -> 2026-09-01
-- -----------------------------------------------------------------------------
CREATE TABLE crm_portfoliohandover (
    id              BIGINT         NOT NULL AUTO_INCREMENT,
    creditor_id      BIGINT         NOT NULL,
    period_month          DATE           NOT NULL,
    overdue_bracket    VARCHAR(20)    NOT NULL,
    debtor_count    INT UNSIGNED   NOT NULL DEFAULT 0,
    average_debt_clp  DECIMAL(12,2)  NOT NULL DEFAULT 0,
    received_at     DATETIME(6)        NULL,
    created_at      DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_handover      PRIMARY KEY (id),
    CONSTRAINT uq_handover_slot UNIQUE (creditor_id, period_month, overdue_bracket),

    CONSTRAINT fk_handover_creditor FOREIGN KEY (creditor_id)
        REFERENCES crm_creditor (id) ON DELETE CASCADE,

    CONSTRAINT ck_handover_bracket CHECK (
        overdue_bracket IN ('1-30', '31-90', '91-120')
    ),
    CONSTRAINT ck_handover_debt CHECK (average_debt_clp >= 0),

    INDEX ix_handover_creditor_period (creditor_id, period_month)
) ENGINE=InnoDB;


-- =============================================================================
--  C. CAMPANAS Y METRICAS
-- =============================================================================

-- -----------------------------------------------------------------------------
--  crm_campaign — una campana de contacto sobre la cartera de una empresa.
--  channels : JSON con la lista de canales -> ["whatsapp", "sms", "email"]
-- -----------------------------------------------------------------------------
CREATE TABLE crm_campaign (
    id            BIGINT            NOT NULL AUTO_INCREMENT,
    creditor_id    BIGINT            NOT NULL,
    name          VARCHAR(120)      NOT NULL,
    starts_on     DATE              NOT NULL,
    ends_on       DATE                  NULL,
    status        VARCHAR(20)       NOT NULL DEFAULT 'draft',
    channels      JSON              NOT NULL,
    contact_attempts   SMALLINT UNSIGNED NOT NULL DEFAULT 3,
    created_at    DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at    DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                             ON UPDATE CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_campaign      PRIMARY KEY (id),
    -- Una empresa no puede tener dos campanas con el mismo nombre.
    CONSTRAINT uq_campaign_name UNIQUE (creditor_id, name),

    CONSTRAINT fk_campaign_creditor FOREIGN KEY (creditor_id)
        REFERENCES crm_creditor (id) ON DELETE CASCADE,

    CONSTRAINT ck_campaign_status CHECK (
        status IN ('draft', 'running', 'paused', 'finished')
    ),
    CONSTRAINT ck_campaign_dates CHECK (ends_on IS NULL OR ends_on >= starts_on),
    CONSTRAINT ck_campaign_attempts CHECK (contact_attempts BETWEEN 1 AND 10),

    INDEX ix_campaign_creditor_status (creditor_id, status),
    INDEX ix_campaign_starts (starts_on)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
--  crm_campaignfunnelsnapshot — el embudo medido, por campana y fecha de corte.
--
--  El embudo de APOFYX TERMINA EN EL CLIC (docs §11.1). No hay columna de
--  pagos ni de recaudacion porque APOFYX no los puede medir: le llegan despues
--  en una planilla del acreedor (§11.3). La ausencia de esa columna es el
--  hallazgo del caso traducido a esquema.
--
--  Los CHECK replican la logica del embudo: no se puede entregar mas de lo
--  enviado, ni abrir mas de lo entregado.
-- -----------------------------------------------------------------------------
CREATE TABLE crm_campaignfunnelsnapshot (
    id             BIGINT        NOT NULL AUTO_INCREMENT,
    campaign_id    BIGINT        NOT NULL,
    measured_on    DATE          NOT NULL,
    messages_sent           INT UNSIGNED  NOT NULL DEFAULT 0,
    messages_delivered      INT UNSIGNED  NOT NULL DEFAULT 0,
    messages_opened         INT UNSIGNED  NOT NULL DEFAULT 0,
    replies_received        INT UNSIGNED  NOT NULL DEFAULT 0,
    link_clicks         INT UNSIGNED  NOT NULL DEFAULT 0,
    fraud_reports   INT UNSIGNED  NOT NULL DEFAULT 0,
    optout_requests        INT UNSIGNED  NOT NULL DEFAULT 0,
    debt_disputes       INT UNSIGNED  NOT NULL DEFAULT 0,
    created_at     DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_snapshot      PRIMARY KEY (id),
    CONSTRAINT uq_snapshot_slot UNIQUE (campaign_id, measured_on),

    CONSTRAINT fk_snapshot_campaign FOREIGN KEY (campaign_id)
        REFERENCES crm_campaign (id) ON DELETE CASCADE,

    CONSTRAINT ck_snapshot_delivered CHECK (messages_delivered <= messages_sent),
    CONSTRAINT ck_snapshot_opened    CHECK (messages_opened    <= messages_delivered),

    INDEX ix_snapshot_campaign_date (campaign_id, measured_on)
) ENGINE=InnoDB;


-- =============================================================================
--  D. ASISTENTE DEL SITIO
-- =============================================================================

-- -----------------------------------------------------------------------------
--  assistant_intent — catalogo de intenciones (docs §9.2).
--  audience: a que publico de §6.3 apunta la intencion.
--  tiebreak_priority: desempata cuando dos intenciones puntuan igual. Menor gana.
-- -----------------------------------------------------------------------------
CREATE TABLE assistant_intent (
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    slug          VARCHAR(60)  NOT NULL,
    name          VARCHAR(120) NOT NULL,
    audience      VARCHAR(20)  NOT NULL DEFAULT 'general',
    description   VARCHAR(255)     NULL,
    tiebreak_priority      SMALLINT     NOT NULL DEFAULT 100,
    is_active     BOOL         NOT NULL DEFAULT TRUE,
    created_at    DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at    DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                        ON UPDATE CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_intent      PRIMARY KEY (id),
    CONSTRAINT uq_intent_slug UNIQUE (slug),

    CONSTRAINT ck_intent_audience CHECK (
        audience IN ('prospect', 'debtor', 'general')
    ),

    INDEX ix_intent_audience (audience, is_active)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
--  assistant_intentpattern — frases y palabras clave que disparan la intencion.
--
--  text se guarda YA NORMALIZADO: minusculas, sin tildes, sin puntuacion.
--  De ese modo la comparacion en tiempo de ejecucion es directa y no depende
--  de como haya escrito el visitante.
--
--  match_weight permite que una frase completa pese mas que una palabra suelta.
-- -----------------------------------------------------------------------------
CREATE TABLE assistant_intentpattern (
    id          BIGINT        NOT NULL AUTO_INCREMENT,
    intent_id   BIGINT        NOT NULL,
    `pattern_text`      VARCHAR(200)  NOT NULL,
    match_weight      DECIMAL(4,2)  NOT NULL DEFAULT 1.00,
    created_at  DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_pattern      PRIMARY KEY (id),
    CONSTRAINT uq_pattern_text UNIQUE (intent_id, `pattern_text`),

    CONSTRAINT fk_pattern_intent FOREIGN KEY (intent_id)
        REFERENCES assistant_intent (id) ON DELETE CASCADE,

    CONSTRAINT ck_pattern_match_weight CHECK (match_weight > 0),

    INDEX ix_pattern_intent (intent_id),
    INDEX ix_pattern_text   (`pattern_text`)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
--  assistant_intentresponse — respuestas aprobadas para cada intencion.
--
--  Estas son las respuestas que NO se generan nunca con el LLM: precios,
--  plazos y tratamiento de datos son declaraciones comerciales y legales de
--  la empresa, y salen siempre de aca (docs §9.3).
--
--  suggested_action: accion que la interfaz ofrece junto a la respuesta,
--                    por ejemplo 'schedule_demo' o 'show_plans'.
-- -----------------------------------------------------------------------------
CREATE TABLE assistant_intentresponse (
    id                BIGINT       NOT NULL AUTO_INCREMENT,
    intent_id         BIGINT       NOT NULL,
    `response_text`            TEXT         NOT NULL,
    display_order          SMALLINT     NOT NULL DEFAULT 0,
    suggested_action  VARCHAR(40)      NULL,
    is_active         BOOL         NOT NULL DEFAULT TRUE,
    created_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                            ON UPDATE CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_response      PRIMARY KEY (id),
    CONSTRAINT uq_response_slot UNIQUE (intent_id, display_order),

    CONSTRAINT fk_response_intent FOREIGN KEY (intent_id)
        REFERENCES assistant_intent (id) ON DELETE CASCADE,

    INDEX ix_response_intent (intent_id)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
--  assistant_conversation — una sesion de chat en el sitio.
--
--  No hay FK a usuario: el visitante es anonimo. session_key es un UUID que
--  genera el navegador, no identifica a una persona.
-- -----------------------------------------------------------------------------
CREATE TABLE assistant_conversation (
    id                 BIGINT       NOT NULL AUTO_INCREMENT,
    session_key        VARCHAR(64)  NOT NULL,
    inferred_audience  VARCHAR(20)      NULL,
    is_resolved        BOOL         NOT NULL DEFAULT FALSE,
    started_at         DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    last_activity_at   DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                             ON UPDATE CURRENT_TIMESTAMP(6),
    user_agent         VARCHAR(255)     NULL,

    CONSTRAINT pk_conversation PRIMARY KEY (id),

    CONSTRAINT ck_conversation_audience CHECK (
        inferred_audience IS NULL
        OR inferred_audience IN ('prospect', 'debtor', 'general')
    ),

    INDEX ix_conversation_session (session_key),
    INDEX ix_conversation_started (started_at)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
--  assistant_message — cada turno de la conversacion.
--
--  source es la columna clave para la defensa: dice si la respuesta salio del
--  catalogo de reglas, del LLM o del fallback. Con eso el panel puede mostrar
--  que porcentaje resolvio cada motor (docs §9.3).
--
--  El CHECK ck_message_engine obliga a que los mensajes del visitante no
--  traigan origen ni confianza: esas columnas solo aplican al asistente.
-- -----------------------------------------------------------------------------
CREATE TABLE assistant_message (
    id               BIGINT         NOT NULL AUTO_INCREMENT,
    conversation_id  BIGINT         NOT NULL,
    speaker             VARCHAR(10)    NOT NULL,
    `message_text`           TEXT           NOT NULL,
    intent_id        BIGINT             NULL,
    match_confidence       DECIMAL(5,4)       NULL,
    answer_engine           VARCHAR(10)        NULL,
    response_time_ms       INT UNSIGNED       NULL,
    created_at       DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_message PRIMARY KEY (id),

    CONSTRAINT fk_message_conversation FOREIGN KEY (conversation_id)
        REFERENCES assistant_conversation (id) ON DELETE CASCADE,
    CONSTRAINT fk_message_intent FOREIGN KEY (intent_id)
        REFERENCES assistant_intent (id) ON DELETE SET NULL,

    CONSTRAINT ck_message_speaker CHECK (speaker IN ('visitor', 'assistant')),
    CONSTRAINT ck_message_match_confidence CHECK (
        match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)
    ),
    CONSTRAINT ck_message_engine CHECK (
        (speaker = 'visitor'   AND answer_engine IS NULL)
        OR
        (speaker = 'assistant' AND answer_engine IN ('rules', 'llm', 'fallback'))
    ),

    INDEX ix_message_conversation (conversation_id, created_at),
    INDEX ix_message_engine       (answer_engine),
    INDEX ix_message_intent       (intent_id)
) ENGINE=InnoDB;


-- =============================================================================
--  E. LEADS
--  Va al final porque depende de crm_creditor, crm_industry y
--  assistant_conversation.
-- =============================================================================

-- -----------------------------------------------------------------------------
--  crm_lead — contacto comercial entrante, del formulario o del asistente.
--
--  conversation_id : si el lead nacio en el chat, queda enlazado a esa
--                    conversacion, para poder leer que se hablo.
--  current_collection_method : como gestiona hoy su cartera. Es el dato que mas
--                    califica un lead: quien responde 'nadie' es un cliente
--                    muy distinto de quien ya paga una cobranza externa.
--  creditor_id      : se llena solo si el lead termina convirtiendose en cliente.
-- -----------------------------------------------------------------------------
CREATE TABLE crm_lead (
    id               BIGINT        NOT NULL AUTO_INCREMENT,
    full_name          VARCHAR(120)    NOT NULL,
    job_title          VARCHAR(80)         NULL,
    company_name       VARCHAR(160)    NOT NULL,
    email              VARCHAR(254)    NOT NULL,
    phone              VARCHAR(20)         NULL,
    estimated_debtor_count     INT UNSIGNED        NULL,
    estimated_overdue_clp     BIGINT UNSIGNED     NULL,
    current_collection_method VARCHAR(20)         NULL,
    industry_id      BIGINT            NULL,
    source           VARCHAR(20)   NOT NULL DEFAULT 'form',
    status           VARCHAR(20)   NOT NULL DEFAULT 'new',
    inquiry_message  TEXT              NULL,
    conversation_id  BIGINT            NULL,
    converted_creditor_id BIGINT        NULL,
    created_at       DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at       DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                            ON UPDATE CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_lead PRIMARY KEY (id),

    CONSTRAINT fk_lead_industry FOREIGN KEY (industry_id)
        REFERENCES crm_industry (id) ON DELETE SET NULL,
    CONSTRAINT fk_lead_conversation FOREIGN KEY (conversation_id)
        REFERENCES assistant_conversation (id) ON DELETE SET NULL,
    CONSTRAINT fk_lead_creditor FOREIGN KEY (converted_creditor_id)
        REFERENCES crm_creditor (id) ON DELETE SET NULL,

    CONSTRAINT ck_lead_source CHECK (source IN ('form', 'assistant')),
    -- Los valores van en espanol a proposito (D12): aca no se guarda un estado
    -- interno del sistema sino lo que el lead declara de su propia operacion.
    CONSTRAINT ck_lead_collection_method CHECK (
        current_collection_method IS NULL
        OR current_collection_method IN ('nadie', 'llamadas', 'mensajes', 'externo', 'mixto')
    ),
    CONSTRAINT ck_lead_status CHECK (
        status IN ('new', 'contacted', 'qualified', 'converted', 'discarded')
    ),
    --  REGLA QUE NO SE PUEDE EXPRESAR AQUI
    --  "un lead convertido debe apuntar a una empresa" seria el CHECK
    --      status <> 'converted' OR converted_creditor_id IS NOT NULL
    --  pero MySQL lo rechaza (error 3823): la columna ya participa en una FK
    --  con ON DELETE SET NULL, y ambas reglas se contradicen. Si se borrara la
    --  acreedora, la FK la pondria en NULL y el CHECK quedaria violado.
    --  Se valida en la capa de aplicacion, en el modelo Lead de Django.

    INDEX ix_lead_status  (status, created_at),
    INDEX ix_lead_email   (email),
    INDEX ix_lead_source  (source)
) ENGINE=InnoDB;


-- =============================================================================
--  F. CARTERA RECIBIDA
--
--  Lo que los acreedores le entregan a APOFYX para cobrar. Sin esto APOFYX no
--  tiene nada que trabajar y no podria operar con la plataforma de pagos
--  caida.
--
--  SIGUE SIN HABER TABLAS DE PAGO NI DE TRANSACCION. El dinero lo mueve
--  DataBridge; aca solo llega el aviso y cambia el estado de la deuda.
--
--  NOTA SOBRE ESTAS CINCO TABLAS
--  A diferencia de las de arriba, estas nacieron en los modelos de Django y
--  sus CHECK viajan en la migracion (models.CheckConstraint). Eso significa
--  que la base de pruebas SI las tiene, y que una prueba puede detectar un
--  valor invalido. Las tablas mas antiguas no tienen esa suerte: sus CHECK
--  existen solo aca, y por eso hace falta EsquemaYModelosCalzan en crm/tests.
--
--  Cuando Django crea estas tablas agrega ademas un CHECK redundante (>= 0)
--  por cada columna PositiveInteger. No se escriben aca: INT UNSIGNED ya dice
--  lo mismo.
-- =============================================================================

-- -----------------------------------------------------------------------------
--  cartera_batch — una entrega de cartera, con su fecha de corte.
--
--  No confundir con crm_portfoliohandover, que es el agregado comercial por
--  tramo de mora que muestra el panel. Esto es la entrega real.
--
--  payload_hash : huella del contenido recibido. Sirve para distinguir un
--                 reenvio identico —al que se le responde lo mismo— de un
--                 lote con el mismo id y otro contenido, que se rechaza.
-- -----------------------------------------------------------------------------
CREATE TABLE cartera_batch (
    id              BIGINT        NOT NULL AUTO_INCREMENT,
    creditor_id     BIGINT        NOT NULL,
    external_id     VARCHAR(64)   NOT NULL,
    cut_off         DATE          NOT NULL,
    campaign_id     BIGINT            NULL,
    source          VARCHAR(10)   NOT NULL DEFAULT 'api',
    status          VARCHAR(20)   NOT NULL DEFAULT 'received',
    received_count  INT UNSIGNED  NOT NULL DEFAULT 0,
    accepted_count  INT UNSIGNED  NOT NULL DEFAULT 0,
    rejected_count  INT UNSIGNED  NOT NULL DEFAULT 0,
    payload_hash    VARCHAR(64)   NOT NULL,
    response        JSON          NOT NULL,
    received_at     DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_batch          PRIMARY KEY (id),
    -- El numero de lote es del acreedor: es unico para el, no para todos.
    CONSTRAINT uq_batch_external UNIQUE (creditor_id, external_id),

    CONSTRAINT fk_batch_creditor FOREIGN KEY (creditor_id)
        REFERENCES crm_creditor (id) ON DELETE RESTRICT,
    CONSTRAINT fk_batch_campaign FOREIGN KEY (campaign_id)
        REFERENCES crm_campaign (id) ON DELETE SET NULL,

    CONSTRAINT ck_batch_source CHECK (source IN ('api', 'file')),
    CONSTRAINT ck_batch_status CHECK (
        status IN ('received', 'processed', 'rejected')
    ),

    INDEX ix_batch_campaign (campaign_id)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
--  cartera_debtor — quien debe.
--
--  Existe una sola vez por RUT aunque le deba a varios acreedores: es la misma
--  persona, y tenerla dos veces haria imposible saber cuantas veces se le esta
--  escribiendo.
-- -----------------------------------------------------------------------------
CREATE TABLE cartera_debtor (
    id          BIGINT        NOT NULL AUTO_INCREMENT,
    tax_id      VARCHAR(12)   NOT NULL,
    kind        VARCHAR(10)   NOT NULL DEFAULT 'person',
    full_name   VARCHAR(160)  NOT NULL,
    email       VARCHAR(254)      NULL,
    phone       VARCHAR(20)       NULL,
    created_at  DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at  DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                       ON UPDATE CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_debtor        PRIMARY KEY (id),
    CONSTRAINT uq_debtor_tax_id UNIQUE (tax_id),

    CONSTRAINT ck_debtor_kind CHECK (kind IN ('person', 'company')),
    -- Sin correo ni telefono no hay por donde cobrarle. Es la regla que el
    -- contrato de integracion rechaza como 'sin_canal_contacto'.
    CONSTRAINT ck_debtor_contacto CHECK (email IS NOT NULL OR phone IS NOT NULL),
    CONSTRAINT ck_debtor_tax_id CHECK (tax_id REGEXP '^[0-9]{7,8}-[0-9K]$')
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
--  cartera_debt — lo que un deudor le debe a un acreedor.
--
--  external_id es el id que le puso el acreedor y no se toca nunca: es lo que
--  permite que un pago vuelva hasta el contrato que lo origino. Por eso el
--  unico es (acreedor, external_id) y no incluye el lote: la misma deuda
--  puede llegar varias veces, actualizada.
-- -----------------------------------------------------------------------------
CREATE TABLE cartera_debt (
    id               BIGINT        NOT NULL AUTO_INCREMENT,
    creditor_id      BIGINT        NOT NULL,
    debtor_id        BIGINT        NOT NULL,
    external_id      VARCHAR(64)   NOT NULL,
    currency         VARCHAR(3)    NOT NULL DEFAULT 'CLP',
    concept          VARCHAR(200)  NOT NULL,
    refs             JSON          NOT NULL,
    status           VARCHAR(20)   NOT NULL DEFAULT 'open',
    first_batch_id   BIGINT        NOT NULL,
    last_batch_id    BIGINT        NOT NULL,
    withdrawn_reason VARCHAR(30)       NULL,
    created_at       DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at       DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                            ON UPDATE CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_debt          PRIMARY KEY (id),
    CONSTRAINT uq_debt_external UNIQUE (creditor_id, external_id),

    CONSTRAINT fk_debt_creditor FOREIGN KEY (creditor_id)
        REFERENCES crm_creditor (id) ON DELETE RESTRICT,
    CONSTRAINT fk_debt_debtor FOREIGN KEY (debtor_id)
        REFERENCES cartera_debtor (id) ON DELETE RESTRICT,
    CONSTRAINT fk_debt_first_batch FOREIGN KEY (first_batch_id)
        REFERENCES cartera_batch (id) ON DELETE RESTRICT,
    CONSTRAINT fk_debt_last_batch FOREIGN KEY (last_batch_id)
        REFERENCES cartera_batch (id) ON DELETE RESTRICT,

    CONSTRAINT ck_debt_currency CHECK (currency IN ('CLP', 'UF')),
    CONSTRAINT ck_debt_status CHECK (
        status IN ('open', 'repacted', 'paid', 'withdrawn', 'disputed')
    ),

    INDEX ix_debt_creditor_status (creditor_id, status),
    INDEX ix_debt_debtor (debtor_id)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
--  cartera_debtcharge — el desglose de la deuda: el mes, la cuota, la boleta.
--
--  El monto es lo que se debe HOY de ese cargo, no el original. Cuando el
--  acreedor reenvia la deuda con un saldo menor, los cargos se reemplazan:
--  conservar los viejos dejaria a APOFYX cobrando un monto que ya no existe.
-- -----------------------------------------------------------------------------
CREATE TABLE cartera_debtcharge (
    id          BIGINT         NOT NULL AUTO_INCREMENT,
    debt_id     BIGINT         NOT NULL,
    concept     VARCHAR(120)   NOT NULL,
    period      VARCHAR(7)         NULL,
    amount      DECIMAL(14,2)  NOT NULL,
    due_date    DATE           NOT NULL,
    created_at  DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_debtcharge PRIMARY KEY (id),

    CONSTRAINT fk_charge_debt FOREIGN KEY (debt_id)
        REFERENCES cartera_debt (id) ON DELETE CASCADE,

    CONSTRAINT ck_charge_amount CHECK (amount > 0),

    INDEX ix_charge_debt_due (debt_id, due_date)
) ENGINE=InnoDB;


-- =============================================================================
--  G. INTEGRACION
--
--  El borde por donde entra la cartera. Apagado mientras no se emita ninguna
--  clave: sin credenciales nadie puede enviar nada, y APOFYX sigue trabajando
--  con la carga a mano del panel.
-- =============================================================================

-- -----------------------------------------------------------------------------
--  integracion_apikey — la credencial de un acreedor para entregar cartera.
--
--  NO se guarda la clave, se guarda su huella SHA-256. Si alguien se lleva
--  esta tabla no se lleva las claves, y APOFYX tampoco puede recordarsela a
--  nadie: si se pierde, se emite otra. `prefix` esta para poder decir cual es
--  sin revelarla.
-- -----------------------------------------------------------------------------
CREATE TABLE integracion_apikey (
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    creditor_id   BIGINT       NOT NULL,
    name          VARCHAR(80)  NOT NULL,
    key_hash      VARCHAR(64)  NOT NULL,
    prefix        VARCHAR(12)  NOT NULL,
    created_at    DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    last_used_at  DATETIME(6)      NULL,
    revoked_at    DATETIME(6)      NULL,

    CONSTRAINT pk_apikey      PRIMARY KEY (id),
    CONSTRAINT uq_apikey_hash UNIQUE (key_hash),

    CONSTRAINT fk_apikey_creditor FOREIGN KEY (creditor_id)
        REFERENCES crm_creditor (id) ON DELETE CASCADE,

    INDEX ix_apikey_hash     (key_hash),
    INDEX ix_apikey_creditor (creditor_id)
) ENGINE=InnoDB;


-- -----------------------------------------------------------------------------
--  integracion_forward — la bandeja de salida hacia DataBridge.
--
--  POR QUE UNA BANDEJA Y NO UN ENVIO DIRECTO
--  Si el reenvio ocurriera dentro de la operacion que recibe la cartera del
--  cliente, una caida de DataBridge haria fallar la recepcion y el cliente
--  veria un error por algo que no es suyo. Aca la recepcion termina bien, el
--  reenvio queda anotado en la misma transaccion, y sale cuando DataBridge
--  responda.
--
--  external_id : el numero con que APOFYX le presenta el lote a DataBridge.
--                No sirve el del acreedor, porque ahora el emisor es APOFYX y
--                cada emisor numera sus propios lotes.
--  status      : 'waiting' es una entrega sin campana asignada. No se adivina
--                a que campana va: espera a que alguien la asigne.
-- -----------------------------------------------------------------------------
CREATE TABLE integracion_forward (
    id               BIGINT            NOT NULL AUTO_INCREMENT,
    batch_id         BIGINT            NOT NULL,
    external_id      VARCHAR(64)       NOT NULL,
    status           VARCHAR(10)       NOT NULL DEFAULT 'pending',
    attempts         SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    next_attempt_at  DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    sent_at          DATETIME(6)           NULL,
    last_error       VARCHAR(300)          NULL,
    response         JSON              NOT NULL,
    created_at       DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_forward          PRIMARY KEY (id),
    CONSTRAINT uq_forward_batch    UNIQUE (batch_id),
    CONSTRAINT uq_forward_external UNIQUE (external_id),

    CONSTRAINT fk_forward_batch FOREIGN KEY (batch_id)
        REFERENCES cartera_batch (id) ON DELETE CASCADE,

    CONSTRAINT ck_forward_status CHECK (
        status IN ('pending', 'waiting', 'sent', 'failed')
    ),

    --  Por aca entra el despachador: lo pendiente que ya toca reintentar.
    INDEX ix_forward_por_enviar (status, next_attempt_at)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
--  integracion_subscription — a donde avisarle a un cliente lo que pasa con su
--  cartera (contrato 3, eventos de vuelta).
--
--  secret : con el se FIRMA cada aviso, y por eso se guarda en claro: una
--           huella sirve para comparar, no para firmar. En produccion va
--           cifrado con una llave fuera de la base.
--  events : los tipos que el cliente quiere recibir. Vacio = todos.
-- -----------------------------------------------------------------------------
CREATE TABLE integracion_subscription (
    id           BIGINT        NOT NULL AUTO_INCREMENT,
    creditor_id  BIGINT        NOT NULL,
    url          VARCHAR(300)  NOT NULL,
    secret       VARCHAR(120)  NOT NULL,
    events       JSON          NOT NULL,
    active       BOOL          NOT NULL DEFAULT TRUE,
    created_at   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_subscription     PRIMARY KEY (id),
    CONSTRAINT uq_subscription_url UNIQUE (creditor_id, url),

    CONSTRAINT fk_subscription_creditor FOREIGN KEY (creditor_id)
        REFERENCES crm_creditor (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
--  integracion_inboundevent — los eventos que llegan de DataBridge.
--
--  Se guardan todos, se entiendan o no: son el rastro de por que una deuda
--  cambio de estado. event_id deduplica, porque la entrega es "al menos una
--  vez" y el mismo aviso puede llegar dos veces.
--  NO hay aqui montos ni datos del deudor en columnas: el pago es de
--  DataBridge. payload guarda el evento tal como llego, y el evento, por
--  contrato, no trae datos personales.
-- -----------------------------------------------------------------------------
CREATE TABLE integracion_inboundevent (
    id           BIGINT       NOT NULL AUTO_INCREMENT,
    event_id     VARCHAR(64)  NOT NULL,
    type         VARCHAR(30)  NOT NULL,
    occurred_at  DATETIME(6)      NULL,
    debt_id      BIGINT           NULL,
    payload      JSON         NOT NULL,
    result       VARCHAR(80)  NOT NULL,
    received_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_inboundevent       PRIMARY KEY (id),
    CONSTRAINT uq_inboundevent_event UNIQUE (event_id),

    CONSTRAINT fk_inboundevent_debt FOREIGN KEY (debt_id)
        REFERENCES cartera_debt (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
--  integracion_outboundevent — la segunda bandeja de salida: los avisos al
--  cliente.
--
--  Cada evento que llega de DataBridge produce uno nuevo por suscripcion, con
--  id propio y el lote del cliente en vez del de APOFYX. Se escribe en la
--  misma transaccion que recibe: si el cliente esta caido, el aviso espera.
-- -----------------------------------------------------------------------------
CREATE TABLE integracion_outboundevent (
    id               BIGINT            NOT NULL AUTO_INCREMENT,
    event_id         VARCHAR(64)       NOT NULL,
    subscription_id  BIGINT            NOT NULL,
    origin_id        BIGINT                NULL,
    type             VARCHAR(30)       NOT NULL,
    payload          JSON              NOT NULL,
    status           VARCHAR(10)       NOT NULL DEFAULT 'pending',
    attempts         SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    next_attempt_at  DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    delivered_at     DATETIME(6)           NULL,
    last_error       VARCHAR(300)          NULL,
    created_at       DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT pk_outboundevent PRIMARY KEY (id),
    --  El mismo evento no se le manda dos veces a la misma suscripcion.
    CONSTRAINT uq_outboundevent UNIQUE (event_id, subscription_id),

    CONSTRAINT fk_outboundevent_subscription FOREIGN KEY (subscription_id)
        REFERENCES integracion_subscription (id) ON DELETE CASCADE,
    CONSTRAINT fk_outboundevent_origin FOREIGN KEY (origin_id)
        REFERENCES integracion_inboundevent (id) ON DELETE SET NULL,

    CONSTRAINT ck_outboundevent_status CHECK (
        status IN ('pending', 'delivered', 'failed')
    ),

    INDEX ix_outboundevent_por_enviar (status, next_attempt_at)
) ENGINE=InnoDB;


-- =============================================================================
--  H. VISTAS PARA EL PANEL
--  Resuelven las tarjetas de resumen de docs §12.2 sin repetir SQL en Django.
-- =============================================================================

-- -----------------------------------------------------------------------------
--  v_company_overview — una fila por cliente, con su cartera del ultimo periodo.
-- -----------------------------------------------------------------------------
--  OJO: cada empresa tiene VARIAS filas por periodo en crm_portfoliohandover,
--  una por tramo de mora. Por eso la cartera se agrega en una tabla derivada
--  antes de unirla; de lo contrario la vista devolveria tres filas por empresa.
--  El ticket medio se pondera por cantidad de registros, no es un promedio
--  simple de los tres tramos.
CREATE OR REPLACE VIEW v_company_overview AS
SELECT
    c.id                       AS creditor_id,
    c.trade_name,
    c.legal_name,
    c.tax_id,
    c.status,
    i.name                     AS industry,
    c.client_since,
    COALESCE(pf.total_debtors, 0) AS total_debtors,
    COALESCE(pf.average_debt_clp, 0)    AS average_debt_clp,
    pf.period_month                         AS portfolio_period,
    (SELECT COUNT(*) FROM crm_campaign cm
      WHERE cm.creditor_id = c.id AND cm.status = 'running') AS running_campaigns
FROM crm_creditor c
JOIN crm_industry i ON i.id = c.industry_id
LEFT JOIN (
    SELECT
        a.creditor_id,
        a.period_month,
        SUM(a.debtor_count) AS total_debtors,
        ROUND(SUM(a.average_debt_clp * a.debtor_count)
              / NULLIF(SUM(a.debtor_count), 0), 2) AS average_debt_clp
    FROM crm_portfoliohandover a
    JOIN (
        SELECT creditor_id, MAX(period_month) AS period_month
          FROM crm_portfoliohandover
         GROUP BY creditor_id
    ) ultimo
      ON ultimo.creditor_id = a.creditor_id
     AND ultimo.period_month     = a.period_month
    GROUP BY a.creditor_id, a.period_month
) pf ON pf.creditor_id = c.id;


-- -----------------------------------------------------------------------------
--  v_campaign_funnel — embudo acumulado por campana, con las tasas ya
--  calculadas. Termina en el clic, igual que el producto (docs §11.1).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_campaign_funnel AS
SELECT
    cm.id            AS campaign_id,
    cm.creditor_id,
    cm.name          AS campaign,
    cm.status,
    SUM(m.messages_sent)          AS messages_sent,
    SUM(m.messages_delivered)     AS messages_delivered,
    SUM(m.messages_opened)        AS messages_opened,
    SUM(m.replies_received)       AS replies_received,
    SUM(m.link_clicks)        AS link_clicks,
    SUM(m.fraud_reports)  AS fraud_reports,
    SUM(m.optout_requests)       AS optout_requests,
    ROUND(100 * SUM(m.messages_delivered) / NULLIF(SUM(m.messages_sent), 0),      2) AS delivery_rate,
    ROUND(100 * SUM(m.messages_opened)    / NULLIF(SUM(m.messages_delivered), 0), 2) AS open_rate,
    ROUND(100 * SUM(m.link_clicks)    / NULLIF(SUM(m.messages_opened), 0),    2) AS click_rate,
    -- La razon entre reportes de fraude y clics: el numero que define el caso.
    ROUND(SUM(m.fraud_reports) / NULLIF(SUM(m.link_clicks), 0),       3) AS spam_per_click
FROM crm_campaign cm
LEFT JOIN crm_campaignfunnelsnapshot m ON m.campaign_id = cm.id
GROUP BY cm.id, cm.creditor_id, cm.name, cm.status;


-- -----------------------------------------------------------------------------
--  v_assistant_coverage — que porcentaje de las respuestas resolvio cada motor.
--  Es la metrica de cobertura del catalogo de intenciones (docs §9.3).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_assistant_coverage AS
SELECT
    DATE(created_at)                                          AS day_at,
    COUNT(*)                                                  AS answers,
    SUM(answer_engine = 'rules')                               AS from_rules,
    SUM(answer_engine = 'llm')                                 AS from_llm,
    SUM(answer_engine = 'fallback')                            AS from_fallback,
    ROUND(100 * SUM(answer_engine = 'rules')    / COUNT(*), 2) AS pct_rules,
    ROUND(100 * SUM(answer_engine = 'llm')      / COUNT(*), 2) AS pct_llm,
    ROUND(100 * SUM(answer_engine = 'fallback') / COUNT(*), 2) AS pct_fallback
FROM assistant_message
WHERE speaker = 'assistant'
GROUP BY DATE(created_at);

-- =============================================================================
--  PARTE 2 — DML · DATOS DE REFERENCIA
-- =============================================================================
--  Rubros atendidos. El sitio los lee desde aca en vez de tenerlos escritos
--  en el HTML (docs §12.1).
--
--  NO hay tabla de planes: APOFYX no publica tarifas. El sitio lleva siempre
--  al formulario de contacto y el valor se cotiza caso a caso.
-- =============================================================================



-- -----------------------------------------------------------------------------
--  Rubros atendidos (docs §4)
-- -----------------------------------------------------------------------------
INSERT INTO crm_industry (name, slug, description) VALUES
    ('Gimnasios y fitness',      'gimnasios',
     'Cadenas y centros deportivos con cuotas mensuales.'),
    ('Educación',                'educacion',
     'Institutos profesionales, preuniversitarios y colegios particulares.'),
    ('Salud',                    'salud',
     'Clínicas dentales, centros médicos y veterinarias con tratamientos en cuotas.'),
    ('Telecomunicaciones',       'telecomunicaciones',
     'ISP regionales y proveedores de televisión e internet.'),
    ('Administración de edificios', 'administracion-edificios',
     'Administradoras de condominios y gastos comunes.'),
    ('Retail especializado',     'retail',
     'Comercio con venta en cuotas propias, sin financiera asociada.'),
    ('Corretaje y arriendos',    'arriendos',
     'Corredoras que administran arriendos y cobran la renta mes a mes.')
AS nuevo
ON DUPLICATE KEY UPDATE
    description = nuevo.description;


-- =============================================================================
--  PARTE 3 — DML · DATOS DE DEMOSTRACION
-- =============================================================================
--  Los cinco clientes de docs §6.1, con sus contactos, carteras, campanas y
--  metricas. Toda la data es SINTETICA: las empresas no existen, los RUT son
--  inventados (con digito verificador valido) y las personas son ficticias.
--
--  Las metricas suman EXACTAMENTE el embudo consolidado de docs §11.1 y §11.2:
--      10.000 deudores · 26.400 enviados · 24.100 entregados
--       6.450 abiertos ·  1.010 respondidos ·   738 clics
--         284 reportes de fraude · 417 opt-outs · 193 disputas
-- =============================================================================



-- -----------------------------------------------------------------------------
--  1. Empresas cliente
-- -----------------------------------------------------------------------------
INSERT INTO crm_creditor
    (legal_name, trade_name, tax_id, industry_id,
     status, client_since, commune, region, website) VALUES
    ('Vitalis Fitness SpA', 'Vitalis Gym', '76543210-3',
     (SELECT id FROM crm_industry WHERE slug = 'gimnasios'),
     'active', '2025-03-10', 'Providencia', 'Metropolitana', 'https://vitalis.cl'),

    ('Instituto Profesional Andes Ltda.', 'Instituto Andes', '77812341-K',
     (SELECT id FROM crm_industry WHERE slug = 'educacion'),
     'active', '2025-07-01', 'Santiago', 'Metropolitana', 'https://ipandes.cl'),

    ('Servicios Dentales Sonrisa Norte SpA', 'Clínica Dental Sonrisa Norte', '76998877-7',
     (SELECT id FROM crm_industry WHERE slug = 'salud'),
     'active', '2025-09-22', 'La Serena', 'Coquimbo', 'https://sonrisanorte.cl'),

    ('NetSur Telecomunicaciones Ltda.', 'NetSur ISP', '78123456-7',
     (SELECT id FROM crm_industry WHERE slug = 'telecomunicaciones'),
     'active', '2026-01-15', 'Valdivia', 'Los Ríos', 'https://netsur.cl'),

    ('Administradora Torres del Parque SpA', 'Torres del Parque', '77456789-5',
     (SELECT id FROM crm_industry WHERE slug = 'administracion-edificios'),
     'active', '2026-04-02', 'Ñuñoa', 'Metropolitana', NULL),

    -- El acreedor que entrega su cartera por el contrato de integracion: una
    -- corredora que administra arriendos, y cuyos morosos son arrendatarios.
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


-- -----------------------------------------------------------------------------
--  2. Contactos
--  Recordar: la restriccion uq_contact_primary permite a lo mas UN contacto
--  principal por empresa.
-- -----------------------------------------------------------------------------
INSERT INTO crm_creditorcontact
    (creditor_id, full_name, job_title, email, phone, is_primary) VALUES
    ((SELECT id FROM crm_creditor WHERE tax_id = '76543210-3'),
     'Paulina Cortés', 'Gerenta de Administración y Finanzas',
     'pcortes@vitalis.cl', '+56912340001', TRUE),
    ((SELECT id FROM crm_creditor WHERE tax_id = '76543210-3'),
     'Rodrigo Muñoz', 'Jefe de Cobranza',
     'rmunoz@vitalis.cl', '+56912340002', FALSE),

    ((SELECT id FROM crm_creditor WHERE tax_id = '77812341-K'),
     'Héctor Salazar', 'Director de Administración',
     'hsalazar@ipandes.cl', '+56912340003', TRUE),

    ((SELECT id FROM crm_creditor WHERE tax_id = '76998877-7'),
     'Valentina Reyes', 'Subgerenta de Finanzas',
     'vreyes@sonrisanorte.cl', '+56912340004', TRUE),

    ((SELECT id FROM crm_creditor WHERE tax_id = '78123456-7'),
     'Cristián Aguilar', 'Gerente General',
     'caguilar@netsur.cl', '+56912340005', TRUE),

    ((SELECT id FROM crm_creditor WHERE tax_id = '77456789-5'),
     'Marisol Tapia', 'Administradora',
     'mtapia@torresdelparque.cl', '+56912340006', TRUE),

    ((SELECT id FROM crm_creditor WHERE tax_id = '76418902-7'),
     'Elena Vargas Mendoza', 'Directora general',
     'elena.vargas@patrimonioinmuebles.cl', '+56981234401', TRUE)
AS nuevo
ON DUPLICATE KEY UPDATE
    full_name  = nuevo.full_name,
    job_title  = nuevo.job_title,
    phone      = nuevo.phone,
    is_primary = nuevo.is_primary;


-- -----------------------------------------------------------------------------
--  3. Cartera entregada — periodo agosto 2026
--  Los totales por empresa calzan con docs §6.1 y suman 10.000 deudores.
-- -----------------------------------------------------------------------------
INSERT INTO crm_portfoliohandover
    (creditor_id, period_month, overdue_bracket, debtor_count, average_debt_clp, received_at) VALUES
    -- Vitalis Gym — 6.200 deudores, ticket medio $41.300
    ((SELECT id FROM crm_creditor WHERE tax_id='76543210-3'), '2026-08-01', '1-30',   3100,  38900.00, '2026-08-02 09:14:00'),
    ((SELECT id FROM crm_creditor WHERE tax_id='76543210-3'), '2026-08-01', '31-90',  2200,  42700.00, '2026-08-02 09:14:00'),
    ((SELECT id FROM crm_creditor WHERE tax_id='76543210-3'), '2026-08-01', '91-120',  900,  45100.00, '2026-08-02 09:14:00'),
    -- Instituto Andes — 980 deudores, ticket medio $268.000
    ((SELECT id FROM crm_creditor WHERE tax_id='77812341-K'), '2026-08-01', '1-30',    320, 248000.00, '2026-08-03 11:02:00'),
    ((SELECT id FROM crm_creditor WHERE tax_id='77812341-K'), '2026-08-01', '31-90',   430, 271000.00, '2026-08-03 11:02:00'),
    ((SELECT id FROM crm_creditor WHERE tax_id='77812341-K'), '2026-08-01', '91-120',  230, 289000.00, '2026-08-03 11:02:00'),
    -- Clinica Dental Sonrisa Norte — 1.450 deudores, ticket medio $184.000
    ((SELECT id FROM crm_creditor WHERE tax_id='76998877-7'), '2026-08-01', '1-30',    700, 171000.00, '2026-08-03 15:40:00'),
    ((SELECT id FROM crm_creditor WHERE tax_id='76998877-7'), '2026-08-01', '31-90',   520, 190000.00, '2026-08-03 15:40:00'),
    ((SELECT id FROM crm_creditor WHERE tax_id='76998877-7'), '2026-08-01', '91-120',  230, 203000.00, '2026-08-03 15:40:00'),
    -- NetSur ISP — 1.100 deudores, ticket medio $27.400
    ((SELECT id FROM crm_creditor WHERE tax_id='78123456-7'), '2026-08-01', '1-30',    640,  25900.00, '2026-08-04 08:20:00'),
    ((SELECT id FROM crm_creditor WHERE tax_id='78123456-7'), '2026-08-01', '31-90',   350,  28300.00, '2026-08-04 08:20:00'),
    ((SELECT id FROM crm_creditor WHERE tax_id='78123456-7'), '2026-08-01', '91-120',  110,  31700.00, '2026-08-04 08:20:00'),
    -- Torres del Parque — 270 deudores, ticket medio $198.000
    ((SELECT id FROM crm_creditor WHERE tax_id='77456789-5'), '2026-08-01', '1-30',     90, 176000.00, '2026-08-05 17:05:00'),
    ((SELECT id FROM crm_creditor WHERE tax_id='77456789-5'), '2026-08-01', '31-90',   110, 199000.00, '2026-08-05 17:05:00'),
    ((SELECT id FROM crm_creditor WHERE tax_id='77456789-5'), '2026-08-01', '91-120',   70, 224000.00, '2026-08-05 17:05:00')
AS nuevo
ON DUPLICATE KEY UPDATE
    debtor_count   = nuevo.debtor_count,
    average_debt_clp = nuevo.average_debt_clp,
    received_at    = nuevo.received_at;


-- -----------------------------------------------------------------------------
--  4. Campanas de agosto 2026 (cerradas)
-- -----------------------------------------------------------------------------
INSERT INTO crm_campaign
    (creditor_id, name, starts_on, ends_on, status, channels, contact_attempts) VALUES
    ((SELECT id FROM crm_creditor WHERE tax_id='76543210-3'),
     'Vitalis - Mora temprana - Agosto 2026', '2026-08-05', '2026-08-31', 'finished',
     JSON_ARRAY('whatsapp','sms','email'), 3),
    ((SELECT id FROM crm_creditor WHERE tax_id='77812341-K'),
     'Andes - Aranceles - Agosto 2026',      '2026-08-06', '2026-08-31', 'finished',
     JSON_ARRAY('whatsapp','email'), 3),
    ((SELECT id FROM crm_creditor WHERE tax_id='76998877-7'),
     'Sonrisa Norte - Tratamientos - Agosto 2026', '2026-08-06', '2026-08-31', 'finished',
     JSON_ARRAY('whatsapp','sms'), 3),
    ((SELECT id FROM crm_creditor WHERE tax_id='78123456-7'),
     'NetSur - Planes impagos - Agosto 2026', '2026-08-07', '2026-08-31', 'finished',
     JSON_ARRAY('sms','email'), 3),
    ((SELECT id FROM crm_creditor WHERE tax_id='77456789-5'),
     'Torres del Parque - Gastos comunes - Agosto 2026', '2026-08-08', '2026-08-31', 'finished',
     JSON_ARRAY('whatsapp','email'), 2),
    -- La que recibe la cartera de arriendos de Patrimonio. Es la unica en curso
    -- de ese acreedor, asi que el reenvio a DataBridge la asigna solo.
    ((SELECT id FROM crm_creditor WHERE tax_id='76418902-7'),
     'Patrimonio - Arriendos - Septiembre 2026', '2026-09-19', NULL, 'running',
     JSON_ARRAY('whatsapp','email'), 5)
AS nuevo
ON DUPLICATE KEY UPDATE
    starts_on   = nuevo.starts_on,
    ends_on     = nuevo.ends_on,
    status      = nuevo.status,
    channels    = nuevo.channels,
    contact_attempts = nuevo.contact_attempts;


-- -----------------------------------------------------------------------------
--  5. Metricas del cierre de agosto
--
--  Las columnas llegan hasta CLICKS y no mas alla: el embudo de APOFYX termina
--  ahi (docs §11.1). Los 189 pagos del informe NO estan en esta tabla porque
--  APOFYX no los mide — los recibe despues en una planilla del acreedor.
--
--  Fijarse en fraud_reports contra link_clicks: 284 contra 738.
-- -----------------------------------------------------------------------------
--  Las tasas NO son iguales entre campanas: cada rubro se comporta distinto, y
--  el comportamiento esta calzado con las personas de docs §6.2.
--      Andes  -> estudiantes: abren mucho (34%) pero hacen clic poco (8%).
--                Es el perfil de Diego, que mira y no actua.
--      NetSur -> publico mayor: abren poco (19%) y reportan fraude mas que
--                nadie. Es el perfil de Rosa, a quien le ensenaron a no hacer
--                clic en links.
--      Torres -> profesionales: la mejor tasa de clic (17%). Es el perfil de
--                Ignacio, que quiere pagar pero exige respaldo.
INSERT INTO crm_campaignfunnelsnapshot
    (campaign_id, measured_on, messages_sent, messages_delivered, messages_opened, replies_received, link_clicks,
     fraud_reports, optout_requests, debt_disputes) VALUES
    ((SELECT id FROM crm_campaign WHERE name='Vitalis - Mora temprana - Agosto 2026'),
     '2026-08-31', 16368, 14994, 4003, 608, 473, 170, 250, 112),
    ((SELECT id FROM crm_campaign WHERE name='Andes - Aranceles - Agosto 2026'),
     '2026-08-31',  2587,  2406,  818,  98,  65,  22,  38,  24),
    ((SELECT id FROM crm_campaign WHERE name='Sonrisa Norte - Tratamientos - Agosto 2026'),
     '2026-08-31',  3828,  3445,  930, 167, 121,  38,  58,  30),
    ((SELECT id FROM crm_campaign WHERE name='NetSur - Planes impagos - Agosto 2026'),
     '2026-08-31',  2904,  2585,  491, 108,  44,  45,  60,  20),
    ((SELECT id FROM crm_campaign WHERE name='Torres del Parque - Gastos comunes - Agosto 2026'),
     '2026-08-31',   713,   670,  208,  29,  35,   9,  11,   7)
AS nuevo
ON DUPLICATE KEY UPDATE
    messages_sent         = nuevo.messages_sent,
    messages_delivered    = nuevo.messages_delivered,
    messages_opened       = nuevo.messages_opened,
    replies_received      = nuevo.replies_received,
    link_clicks       = nuevo.link_clicks,
    fraud_reports = nuevo.fraud_reports,
    optout_requests      = nuevo.optout_requests,
    debt_disputes     = nuevo.debt_disputes;


-- -----------------------------------------------------------------------------
--  6. Campanas de septiembre, en curso y sin cierre todavia
-- -----------------------------------------------------------------------------
INSERT INTO crm_campaign
    (creditor_id, name, starts_on, ends_on, status, channels, contact_attempts) VALUES
    ((SELECT id FROM crm_creditor WHERE tax_id='76543210-3'),
     'Vitalis - Mora temprana - Septiembre 2026', '2026-09-03', NULL, 'running',
     JSON_ARRAY('whatsapp','sms','email'), 3),
    ((SELECT id FROM crm_creditor WHERE tax_id='76998877-7'),
     'Sonrisa Norte - Tratamientos - Septiembre 2026', '2026-09-04', NULL, 'running',
     JSON_ARRAY('whatsapp','sms'), 3)
AS nuevo
ON DUPLICATE KEY UPDATE
    status   = nuevo.status,
    channels = nuevo.channels;

-- =============================================================================
--  PARTE 4 — DML · CATALOGO DEL ASISTENTE
-- =============================================================================
--  Las intenciones del chatbot del sitio (docs §9.2), con sus patrones de
--  reconocimiento y sus respuestas aprobadas.
--
--  COMO FUNCIONA EL MOTOR (docs §9.3)
--  El texto del visitante se normaliza (minusculas, sin tildes, sin signos) y
--  se compara contra los patrones. Cada coincidencia suma el peso del patron;
--  gana la intencion con mas puntaje. Si nadie supera el umbral, se recurre al
--  LLM de respaldo, y si tampoco hay LLM, se responde con 'fallback'.
--
--  POR ESO LOS PATRONES VAN SIN TILDES: se guardan ya normalizados, para que
--  la comparacion no dependa de como escriba el visitante.
--
--  Las RESPUESTAS si llevan tildes: son texto que lee una persona.
--
--  NINGUNA RESPUESTA SE GENERA CON IA. Precios, plazos y tratamiento de datos
--  son declaraciones comerciales y legales de la empresa: salen de aqui,
--  revisadas. El LLM solo cubre lo que este catalogo no previo.
-- =============================================================================


-- -----------------------------------------------------------------------------
--  4.1 Intenciones
--  audience: a que publico de docs §6.3 apunta cada una.
--  tiebreak_priority: desempata cuando dos intenciones puntuan igual. Menor gana.
-- -----------------------------------------------------------------------------
INSERT INTO assistant_intent (slug, name, audience, description, tiebreak_priority) VALUES
    -- Prospecto B2B: la empresa que evalua contratar
    ('que_es_apofyx',          'Que es APOFYX',                'prospect', 'Explicacion breve de la empresa y a quien sirve.',       30),
    ('como_funciona',          'Como funciona el servicio',    'prospect', 'El recorrido completo, sin jerga.',                      30),
    ('precios_planes',         'Precios y planes',             'prospect', 'Planes, valor en UF y comision de exito.',               20),
    ('rubros_requisitos',      'Rubros y requisitos',          'prospect', 'Que rubros se atienden y cartera minima.',               30),
    ('integracion_datos',      'Integracion de la cartera',    'prospect', 'Formato CSV, campos requeridos y API.',                  30),
    ('seguridad_cumplimiento', 'Seguridad y cumplimiento',     'prospect', 'Marco legal y tratamiento de datos.',                    30),
    ('agendar_demo',           'Agendar una demostracion',     'prospect', 'Flujo multipaso que termina grabando un lead.',          10),
    ('hablar_con_ventas',      'Hablar con ventas',            'prospect', 'Datos de contacto comercial y registro del lead.',       20),

    -- Deudor: el publico mayoritario del sitio (docs §6.3)
    ('recibi_mensaje',         'Recibi un mensaje de ustedes', 'debtor',   'Explica que es APOFYX y por que lo contactaron.',        10),
    ('es_estafa',              'Es esto una estafa',           'debtor',   'Como verificar. Ver el limite honesto de docs §9.4.',    10),
    ('no_es_mi_deuda',         'No es mi deuda',               'debtor',   'Canal de disputa y registro de la consulta.',            10),
    ('no_me_contacten',        'No me contacten mas',          'debtor',   'Registra la solicitud de opt-out.',                      10),
    ('quien_les_dio_mis_datos','De donde sacaron mis datos',   'debtor',   'Explica el mandato de la empresa acreedora.',            10),

    -- Transversales
    ('trabaja_con_nosotros',   'Trabajar en APOFYX',           'general',  'Postulaciones y vacantes.',                              50),
    ('contacto_humano',        'Hablar con una persona',       'general',  'Derivacion al canal humano.',                            20),
    ('saludo',                 'Saludo',                       'general',  'Apertura de la conversacion.',                           90),
    ('despedida',              'Despedida',                    'general',  'Cierre de la conversacion.',                             90),
    ('agradecimiento',         'Agradecimiento',               'general',  'El visitante da las gracias.',                           90),
    ('fallback',               'No se entendio',               'general',  'Red de seguridad: menu con las rutas principales.',     999)
AS nuevo
ON DUPLICATE KEY UPDATE
    name        = nuevo.name,
    audience    = nuevo.audience,
    description = nuevo.description,
    tiebreak_priority    = nuevo.tiebreak_priority;


-- -----------------------------------------------------------------------------
--  4.2 Patrones de reconocimiento
--  Peso 3.00 = frase completa e inequivoca.
--  Peso 2.00 = frase parcial caracteristica.
--  Peso 1.00 = palabra suelta, puede aparecer en varias intenciones.
-- -----------------------------------------------------------------------------
INSERT INTO assistant_intentpattern (intent_id, `pattern_text`, match_weight) VALUES
    -- que_es_apofyx
    ((SELECT id FROM assistant_intent WHERE slug='que_es_apofyx'), 'que es apofyx', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='que_es_apofyx'), 'que hacen ustedes', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='que_es_apofyx'), 'a que se dedican', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='que_es_apofyx'), 'quienes son', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='que_es_apofyx'), 'de que se trata', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='que_es_apofyx'), 'en que consiste', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='que_es_apofyx'), 'informacion de la empresa', 2.00),

    -- como_funciona
    ((SELECT id FROM assistant_intent WHERE slug='como_funciona'), 'como funciona', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='como_funciona'), 'como trabajan', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='como_funciona'), 'como es el proceso', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='como_funciona'), 'como cobran', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='como_funciona'), 'que pasos son', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='como_funciona'), 'como seria el servicio', 2.00),

    -- precios_planes
    ((SELECT id FROM assistant_intent WHERE slug='precios_planes'), 'cuanto cuesta', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='precios_planes'), 'cual es el precio', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='precios_planes'), 'que planes tienen', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='precios_planes'), 'cuanto cobran', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='precios_planes'), 'cuanto vale', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='precios_planes'), 'tarifas', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='precios_planes'), 'comision', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='precios_planes'), 'precio', 1.00),
    ((SELECT id FROM assistant_intent WHERE slug='precios_planes'), 'planes', 1.00),
    ((SELECT id FROM assistant_intent WHERE slug='precios_planes'), 'valores', 1.00),

    -- rubros_requisitos
    ((SELECT id FROM assistant_intent WHERE slug='rubros_requisitos'), 'sirve para mi empresa', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='rubros_requisitos'), 'que rubros atienden', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='rubros_requisitos'), 'trabajan con gimnasios', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='rubros_requisitos'), 'cartera minima', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='rubros_requisitos'), 'requisitos', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='rubros_requisitos'), 'sirve para', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='rubros_requisitos'), 'rubros', 1.00),

    -- integracion_datos
    ((SELECT id FROM assistant_intent WHERE slug='integracion_datos'), 'como les entrego mi cartera', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='integracion_datos'), 'como subo los datos', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='integracion_datos'), 'tienen api', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='integracion_datos'), 'formato del archivo', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='integracion_datos'), 'que campos necesitan', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='integracion_datos'), 'integracion', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='integracion_datos'), 'csv', 2.00),

    -- seguridad_cumplimiento
    ((SELECT id FROM assistant_intent WHERE slug='seguridad_cumplimiento'), 'esto es legal', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='seguridad_cumplimiento'), 'que pasa con los datos', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='seguridad_cumplimiento'), 'proteccion de datos', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='seguridad_cumplimiento'), 'cumplen la ley', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='seguridad_cumplimiento'), 'es seguro', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='seguridad_cumplimiento'), 'seguridad', 1.00),
    ((SELECT id FROM assistant_intent WHERE slug='seguridad_cumplimiento'), 'privacidad', 1.00),

    -- agendar_demo
    ((SELECT id FROM assistant_intent WHERE slug='agendar_demo'), 'quiero una demo', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='agendar_demo'), 'agendar una reunion', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='agendar_demo'), 'quiero contratar', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='agendar_demo'), 'me interesa el servicio', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='agendar_demo'), 'quiero probarlo', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='agendar_demo'), 'demostracion', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='agendar_demo'), 'demo', 1.00),

    -- hablar_con_ventas
    ((SELECT id FROM assistant_intent WHERE slug='hablar_con_ventas'), 'hablar con ventas', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='hablar_con_ventas'), 'contacto comercial', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='hablar_con_ventas'), 'quiero una cotizacion', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='hablar_con_ventas'), 'telefono de contacto', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='hablar_con_ventas'), 'correo de contacto', 2.00),

    -- recibi_mensaje
    ((SELECT id FROM assistant_intent WHERE slug='recibi_mensaje'), 'me llego un mensaje', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='recibi_mensaje'), 'me llego un whatsapp', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='recibi_mensaje'), 'me llego un sms', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='recibi_mensaje'), 'recibi un correo de ustedes', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='recibi_mensaje'), 'me escribieron', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='recibi_mensaje'), 'me estan cobrando', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='recibi_mensaje'), 'dice que debo plata', 2.00),

    -- es_estafa
    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'), 'esto es estafa', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'), 'es una estafa', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'), 'es real', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'), 'es verdad esto', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'), 'me quieren estafar', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'), 'es confiable', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'), 'el link es seguro', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'), 'no conozco apofyx', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'), 'estafa', 1.00),
    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'), 'fraude', 1.00),
    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'), 'phishing', 1.00),

    -- no_es_mi_deuda
    ((SELECT id FROM assistant_intent WHERE slug='no_es_mi_deuda'), 'no es mi deuda', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='no_es_mi_deuda'), 'yo no debo nada', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='no_es_mi_deuda'), 'no soy yo', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='no_es_mi_deuda'), 'se equivocaron de persona', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='no_es_mi_deuda'), 'ya pague esto', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='no_es_mi_deuda'), 'no reconozco la deuda', 3.00),

    -- no_me_contacten
    ((SELECT id FROM assistant_intent WHERE slug='no_me_contacten'), 'no me contacten mas', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='no_me_contacten'), 'saquen mi numero', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='no_me_contacten'), 'dejen de escribirme', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='no_me_contacten'), 'quiero darme de baja', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='no_me_contacten'), 'borren mis datos', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='no_me_contacten'), 'no quiero que me llamen', 2.00),

    -- quien_les_dio_mis_datos
    ((SELECT id FROM assistant_intent WHERE slug='quien_les_dio_mis_datos'), 'de donde sacaron mis datos', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='quien_les_dio_mis_datos'), 'quien les dio mi numero', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='quien_les_dio_mis_datos'), 'como consiguieron mi telefono', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='quien_les_dio_mis_datos'), 'quien les paso mi correo', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='quien_les_dio_mis_datos'), 'de donde sacaron mi telefono', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='quien_les_dio_mis_datos'), 'de donde sacaron', 2.00),

    -- trabaja_con_nosotros
    ((SELECT id FROM assistant_intent WHERE slug='trabaja_con_nosotros'), 'quiero trabajar con ustedes', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='trabaja_con_nosotros'), 'tienen vacantes', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='trabaja_con_nosotros'), 'estan contratando', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='trabaja_con_nosotros'), 'enviar mi curriculum', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='trabaja_con_nosotros'), 'buscan gente', 2.00),

    -- contacto_humano
    ((SELECT id FROM assistant_intent WHERE slug='contacto_humano'), 'quiero hablar con una persona', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='contacto_humano'), 'necesito un humano', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='contacto_humano'), 'no quiero hablar con un bot', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='contacto_humano'), 'atencion al cliente', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='contacto_humano'), 'operador', 1.00),

    -- saludo
    ((SELECT id FROM assistant_intent WHERE slug='saludo'), 'hola', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='saludo'), 'buenas', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='saludo'), 'buenos dias', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='saludo'), 'buenas tardes', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='saludo'), 'buenas noches', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='saludo'), 'que tal', 2.00),

    -- despedida
    ((SELECT id FROM assistant_intent WHERE slug='despedida'), 'chao', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='despedida'), 'adios', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='despedida'), 'hasta luego', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='despedida'), 'nos vemos', 2.00),
    ((SELECT id FROM assistant_intent WHERE slug='despedida'), 'eso era todo', 2.00),

    -- agradecimiento
    ((SELECT id FROM assistant_intent WHERE slug='agradecimiento'), 'gracias', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='agradecimiento'), 'muchas gracias', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='agradecimiento'), 'te agradezco', 3.00),
    ((SELECT id FROM assistant_intent WHERE slug='agradecimiento'), 'gracias por la ayuda', 3.00)
AS nuevo
ON DUPLICATE KEY UPDATE
    match_weight = nuevo.match_weight;


-- -----------------------------------------------------------------------------
--  4.3 Respuestas aprobadas
--  suggested_action es la accion que la interfaz ofrece junto al texto: un
--  boton, un formulario o una tabla que el front renderiza desde la BD.
--  APOFYX no publica tarifas, asi que la respuesta de precios no da numeros:
--  deriva al formulario de contacto con la accion 'contact_sales'.
-- -----------------------------------------------------------------------------
INSERT INTO assistant_intentresponse (intent_id, `response_text`, display_order, suggested_action) VALUES

    ((SELECT id FROM assistant_intent WHERE slug='que_es_apofyx'),
     'APOFYX es una empresa chilena de cobranza asistida por IA. Las empresas nos entregan su cartera morosa y nosotros contactamos a sus clientes por WhatsApp, SMS y correo de forma automatizada. Trabajamos con carteras masivas de ticket bajo, donde tener un call center no se justifica económicamente.',
     0, 'show_how_it_works'),

    ((SELECT id FROM assistant_intent WHERE slug='como_funciona'),
     'El proceso tiene cinco pasos: 1) Su empresa firma el mandato de cobranza y nos entrega la cartera. 2) Normalizamos los datos: validamos RUT, teléfonos y eliminamos duplicados. 3) Un modelo ordena la cartera según probabilidad de pago. 4) Se envían los mensajes según una cadencia programada. 5) Usted sigue el rendimiento desde su panel. Todo el contacto es digital: no hay llamadas.',
     0, 'schedule_demo'),

    ((SELECT id FROM assistant_intent WHERE slug='precios_planes'),
     'No publicamos tarifas: el valor depende del tamaño y la antigüedad de su cartera, y preferimos darle un número real y no uno inventado. Déjenos sus datos en el formulario de contacto y le enviamos una estimación concreta dentro de un día hábil.',
     0, 'contact_sales'),

    ((SELECT id FROM assistant_intent WHERE slug='rubros_requisitos'),
     'Atendemos gimnasios y centros deportivos, educación, salud, telecomunicaciones, administración de edificios y retail con venta en cuotas propias. El requisito práctico es tener al menos unos 200 registros en mora: bajo ese volumen la automatización no se justifica frente a una gestión manual.',
     0, 'show_industries'),

    ((SELECT id FROM assistant_intent WHERE slug='integracion_datos'),
     'Puede entregarnos la cartera de dos formas: subiendo un archivo CSV desde su panel, o conectando nuestra API si prefiere que se sincronice sola. Los campos mínimos son RUT, nombre, teléfono, correo, monto adeudado, fecha de vencimiento, número de documento y sucursal.',
     0, 'show_integration'),

    ((SELECT id FROM assistant_intent WHERE slug='seguridad_cumplimiento'),
     'Operamos como encargados de tratamiento de datos, bajo un mandato de cobranza extrajudicial que firma la empresa acreedora. Respetamos las ventanas horarias de contacto, no contactamos a terceros y atendemos toda solicitud de oposición. El marco aplicable es la Ley 19.496 sobre cobranza extrajudicial y la normativa vigente de protección de datos personales.',
     0, 'show_privacy'),

    ((SELECT id FROM assistant_intent WHERE slug='agendar_demo'),
     'Con gusto. Necesito cuatro datos y el equipo comercial lo contacta dentro de un día hábil. Para empezar: ¿cuál es su nombre completo?',
     0, 'schedule_demo'),

    ((SELECT id FROM assistant_intent WHERE slug='hablar_con_ventas'),
     'Puede escribir a comercial@apofyx.cl o dejarnos sus datos acá mismo y lo contactamos dentro de un día hábil. ¿Qué prefiere?',
     0, 'contact_sales'),

    --  Respuestas al deudor. Ver el limite honesto en docs §9.4: son correctas
    --  y aun asi no resuelven el negocio, porque derivan la verificacion a la
    --  empresa acreedora. Eso es deliberado y es el hallazgo del caso.
    ((SELECT id FROM assistant_intent WHERE slug='recibi_mensaje'),
     'APOFYX gestiona cobranzas por encargo de otras empresas. Si usted recibió un mensaje nuestro, es porque la empresa con la que tiene la deuda nos encargó esa gestión; el nombre de esa empresa aparece en el mensaje. Para confirmarlo con seguridad, comuníquese directamente con ella por los canales que usted ya conoce.',
     0, 'verify_with_creditor'),

    ((SELECT id FROM assistant_intent WHERE slug='es_estafa'),
     'Entiendo la duda, y hace bien en preguntar. APOFYX es una empresa de cobranza que trabaja por encargo de terceros. No le pedimos que confíe en nosotros: le pedimos que verifique con la empresa con la que tiene la deuda, usando el teléfono o la sucursal que usted ya conoce, no los datos que vengan en el mensaje. Nunca le vamos a pedir claves bancarias, ni códigos de verificación, ni datos de su tarjeta.',
     0, 'verify_with_creditor'),

    ((SELECT id FROM assistant_intent WHERE slug='no_es_mi_deuda'),
     'Puede presentar una disputa y se detiene la gestión mientras se revisa. Déjenos su RUT y un correo de contacto y la registramos; la empresa acreedora tiene que responder. Si el mensaje le llegó a un número que cambió de dueño, también corresponde avisarnos para sacarlo de la base.',
     0, 'register_dispute'),

    ((SELECT id FROM assistant_intent WHERE slug='no_me_contacten'),
     'Tiene derecho a oponerse al contacto y lo registramos de inmediato. Indíquenos el número o el correo que quiere dar de baja y dejamos de escribirle. Tenga presente que dar de baja el contacto no elimina la deuda: esa sigue con la empresa acreedora.',
     0, 'register_optout'),

    ((SELECT id FROM assistant_intent WHERE slug='quien_les_dio_mis_datos'),
     'Sus datos nos los entregó la empresa con la que usted tiene la deuda, que nos encargó gestionarla mediante un mandato de cobranza. No compramos bases de datos ni las obtenemos de otras fuentes. Si quiere saber exactamente qué datos tenemos, o pedir que los eliminemos, puede solicitarlo y se lo respondemos.',
     0, 'show_privacy'),

    ((SELECT id FROM assistant_intent WHERE slug='trabaja_con_nosotros'),
     'Somos un equipo chico y publicamos las vacantes cuando las hay. Puede enviar su currículum a personas@apofyx.cl y queda en nuestra base para futuras búsquedas.',
     0, 'show_careers'),

    ((SELECT id FROM assistant_intent WHERE slug='contacto_humano'),
     'Le dejo los canales con personas: para temas comerciales, comercial@apofyx.cl. Si usted recibió un mensaje de cobranza y quiere reclamar o consultar, escriba a contacto@apofyx.cl y le respondemos dentro de dos días hábiles.',
     0, 'contact_sales'),

    ((SELECT id FROM assistant_intent WHERE slug='saludo'),
     'Hola. Soy el asistente automático de APOFYX. Puedo explicarle qué hacemos, cómo funciona el servicio, agendar una demostración, u orientarlo si recibió un mensaje de cobranza nuestro. ¿En qué lo ayudo?',
     0, 'show_menu'),

    ((SELECT id FROM assistant_intent WHERE slug='despedida'),
     'Gracias por escribir. Si necesita algo más, el asistente queda disponible en esta misma página.',
     0, NULL),

    ((SELECT id FROM assistant_intent WHERE slug='agradecimiento'),
     'De nada. Si le queda otra duda, acá sigo.',
     0, NULL),

    --  La respuesta que se usa cuando el motor de reglas no llega al umbral y
    --  tampoco hay LLM disponible. Es la red de seguridad del sistema.
    ((SELECT id FROM assistant_intent WHERE slug='fallback'),
     'No estoy seguro de haber entendido. Puedo ayudarlo con: 1) Qué es APOFYX y cómo funciona. 2) Cómo entregar su cartera. 3) Agendar una demostración. 4) Recibí un mensaje de cobranza de ustedes. Escriba el número o reformule su pregunta.',
     0, 'show_menu')
AS nuevo
ON DUPLICATE KEY UPDATE
    `response_text`  = nuevo.`response_text`,
    suggested_action = nuevo.suggested_action;


-- =============================================================================
--  PARTE 5 — PERMISOS PARA LAS PRUEBAS
-- =============================================================================
--  Django crea una base aparte (test_apofyx) cada vez que corre los tests, y la
--  borra al terminar. El usuario de aplicacion solo tiene permisos sobre
--  'apofyx', asi que sin esto "manage.py test" falla al intentar crearla.
--
--  El patron test\_% cubre cualquier base de prueba, incluidas las paralelas
--  que Django numera (test_apofyx_1, test_apofyx_2, ...).
-- =============================================================================

GRANT ALL PRIVILEGES ON `test\_%`.* TO 'apofyx_app'@'%';
FLUSH PRIVILEGES;


-- =============================================================================
--  PARTE 6 — VERIFICACION FINAL
-- =============================================================================

SELECT '--- Inventario de tablas ---' AS `Resultado`;
-- DATABASE() y no 'apofyx' a secas: con el nombre fijo, correr este archivo en
-- otra base informaba igual sobre apofyx y el inventario mentia. La columna de
-- origen separa las 12 tablas que crea este script de las que agrega Django al
-- migrar (auth_*, django_*), que aparecen aca pero no son parte del DDL.
SELECT TABLE_NAME AS tabla,
       TABLE_ROWS AS filas_aprox,
       CASE WHEN TABLE_NAME LIKE 'crm\_%' OR TABLE_NAME LIKE 'assistant\_%'
            THEN 'este script' ELSE 'Django (migraciones)' END AS origen
  FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'
 ORDER BY origen, TABLE_NAME;

SELECT '--- Embudo cargado, debe calzar con docs §11.1 ---' AS `Resultado`;
SELECT 'Cartera total (deudores)' AS indicador, SUM(debtor_count) AS valor
  FROM crm_portfoliohandover WHERE period_month = '2026-08-01'
UNION ALL SELECT 'Mensajes enviados',  SUM(messages_sent)         FROM crm_campaignfunnelsnapshot
UNION ALL SELECT 'Entregados',         SUM(messages_delivered)    FROM crm_campaignfunnelsnapshot
UNION ALL SELECT 'Abrieron',           SUM(messages_opened)       FROM crm_campaignfunnelsnapshot
UNION ALL SELECT 'Respondieron',       SUM(replies_received)      FROM crm_campaignfunnelsnapshot
UNION ALL SELECT 'Clics',              SUM(link_clicks)       FROM crm_campaignfunnelsnapshot
UNION ALL SELECT 'Reportes de fraude', SUM(fraud_reports) FROM crm_campaignfunnelsnapshot
UNION ALL SELECT 'Opt-outs',           SUM(optout_requests)      FROM crm_campaignfunnelsnapshot
UNION ALL SELECT 'Disputas',           SUM(debt_disputes)     FROM crm_campaignfunnelsnapshot;

SELECT '--- Catalogo del asistente ---' AS `Resultado`;
SELECT i.audience AS publico,
       COUNT(DISTINCT i.id)  AS intenciones,
       COUNT(DISTINCT p.id)  AS patrones,
       COUNT(DISTINCT r.id)  AS respuestas
  FROM assistant_intent i
  LEFT JOIN assistant_intentpattern  p ON p.intent_id = i.id
  LEFT JOIN assistant_intentresponse r ON r.intent_id = i.id
 GROUP BY i.audience WITH ROLLUP;

SELECT '--- Clientes y su cartera ---' AS `Resultado`;
SELECT trade_name, industry, total_debtors, average_debt_clp
  FROM v_company_overview ORDER BY total_debtors DESC;

-- =============================================================================
--  Fin de AphofyxDB.sql
-- =============================================================================
