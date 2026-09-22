# APOFYX

[![CI](https://github.com/TechnicalBridge/APOFYX/actions/workflows/ci.yml/badge.svg)](https://github.com/TechnicalBridge/APOFYX/actions/workflows/ci.yml)

Sitio corporativo y panel de administración de **APOFYX**, una empresa de cobranza
extrajudicial para carteras masivas de ticket bajo.

Proyecto de Capstone. La empresa, los datos y las cifras son ficticios.

```
Django 6.1  ·  MySQL 8.4  ·  Bootstrap 5.3  ·  HTML/CSS/JS sin frameworks
```

---

## Qué es y qué no es

APOFYX gestiona la cobranza de empresas que tienen muchos clientes morosos de monto
bajo —gimnasios, institutos, clínicas, ISP, gastos comunes—, donde una llamada
telefónica cuesta más de lo que recupera.

**APOFYX es puramente operacional.** No procesa pagos y no tiene inteligencia
artificial de ningún tipo: lo que hace es ordenar carteras, mandar mensajes con
plantillas y reportar. La IA y el gestor de pagos los aporta **DataBridge**, el
software de la organización **Technical Bridge**, que vive en otro repositorio.

Esa frontera es lo más importante del proyecto y está explicada en
[`docs/APOFYX.md`](docs/APOFYX.md), §7.3 y §13.

---

## Puesta en marcha

Requiere **Docker Desktop** y **Python 3.14**.

```bash
# 1. Configuración
cp .env.example .env           # en Windows:  copy .env.example .env

# 2. Base de datos: levanta MySQL 8.4 ya poblado
docker compose up -d

# 3. Entorno de Python
python -m venv .venv
.venv\Scripts\activate         # en bash:  source .venv/bin/activate
pip install -r requirements.txt

# 4. Tablas de Django sobre el esquema existente
python manage.py migrate --fake-initial
python manage.py createsuperuser --noinput

# 5. A correr
python manage.py runserver
```

| | |
| --- | --- |
| Sitio | http://127.0.0.1:8000/ |
| Panel | http://127.0.0.1:8000/panel/ · usuario `admin` |
| Admin de Django | http://127.0.0.1:8000/admin/ |
| Base de datos | `127.0.0.1:3307` · usuario `apofyx_app` |

Las credenciales de desarrollo están en `.env.example`. **Cámbialas antes de
mostrar esto a alguien.**

> **`--fake-initial` no es un atajo.** El esquema lo crea `sql/AphofyxDB.sql`, y los
> modelos son su espejo. Con esa bandera Django reconoce las tablas existentes y las
> adopta en vez de intentar crearlas de nuevo. De ahí en adelante mandan las
> migraciones.
>
> La bandera solo cubre las migraciones *iniciales*. Las posteriores que crean algo
> que el DDL ya trae van envueltas en `SiFalta` (`crm/operaciones.py`): en una base
> nueva lo encuentran y siguen; en una antigua lo crean.

---

## Estructura

```
APOFYX/
├── config/            proyecto Django: settings y urls raíz
├── crm/               clientes B2B, carteras, campañas y leads
├── assistant/         catálogo del asistente del sitio y conversaciones
├── cartera/           deudores, deudas y cargos que entregan los acreedores
├── integracion/       el borde: cartera que entra y sale, eventos que vuelven
├── templates/         base, sitio público y panel
├── static/
│   ├── vendor/        Bootstrap y tipografías, en local para no depender de internet
│   ├── css/main.css   capa de tema sobre Bootstrap
│   ├── js/            animaciones
│   └── brand/         logotipo e iconos
├── sql/AphofyxDB.sql  esquema físico completo: DDL + datos
└── docs/APOFYX.md     documento maestro del caso
```

Cuatro apps, y el nombre de cada una define el prefijo de sus tablas: `crm` →
`crm_creditor`, `cartera` → `cartera_debtor`.

---

## Recibir la cartera de un cliente

El acreedor entrega su cartera morosa por `POST /api/v1/carteras`, en el formato
**Cartera v1** del contrato de integración. Primero se le emite su credencial:

```bash
python manage.py emitir_clave 76418902-7 "Servidor de Patrimonio"
```

La clave se muestra **una sola vez**: en la base queda solo su huella SHA-256, así
que no se puede volver a leer. Si se pierde, se emite otra con
`--revocar-anteriores`.

Sin claves emitidas nadie puede enviar nada, y APOFYX funciona igual con la carga
a mano del panel.

### Pasársela a DataBridge

Con `DATABRIDGE_URL` y `DATABRIDGE_CLAVE` en el `.env`, cada entrega aceptada se
reenvía a DataBridge en el mismo formato, con el mandato de APOFYX y la campaña
agregados. Los montos, los cargos y los ids de deuda no se tocan.

El reenvío pasa por una bandeja de salida (`integracion_forward`), así que el
acreedor recibe su respuesta aunque DataBridge esté caído. Lo que no se pudo
entregar se reintenta con esperas crecientes (1 min, 5 min, 30 min, 2 h, 6 h,
24 h) hasta seis veces:

```bash
python manage.py despachar_reenvios      # lo pendiente que ya toca
```

En desarrollo el primer intento sale apenas se recibe, dentro de la misma
petición, y si DataBridge no contesta el acreedor espera ese intento fallido
(unos 2 s con DataBridge apagado; hasta `DATABRIDGE_TIMEOUT_S` si está colgado).
En producción conviene `DATABRIDGE_REENVIO_INMEDIATO=0` y correr
`despachar_reenvios` cada minuto con el programador de tareas: la recepción queda
completamente separada de DataBridge.

Una entrega necesita campaña. Si el acreedor tiene exactamente una en curso, se
usa esa; con cero o con varias queda **esperando campaña** hasta que alguien la
asigne en el panel, y el próximo despacho la retoma.

Sin esas dos variables el reenvío está apagado y APOFYX trabaja solo.

### Los eventos de vuelta

Cuando un deudor paga o acepta un plan en DataBridge, DataBridge le avisa a
APOFYX, APOFYX pone al día la deuda y se lo reporta al cliente con el mismo
formato. Patrimonio marca pagados los cargos del contrato sin saber que detrás
hay DataBridge.

```bash
# 1. APOFYX le dice a DataBridge dónde avisarle. Devuelve el secreto con que
#    DataBridge firma: va al .env como DATABRIDGE_SECRETO_EVENTOS.
python manage.py suscribirse_a_databridge https://apofyx.cl/api/v1/eventos

# 2. APOFYX registra dónde avisarle a cada cliente. Devuelve el secreto que el
#    cliente configura de su lado (en Patrimonio, EVENTOS_SECRET).
python manage.py suscribir_cliente 76418902-7 http://localhost:3001/api/eventos
```

| Evento | Qué le pasa a la deuda en APOFYX |
| --- | --- |
| `pago.confirmado` | Se anota. El estado no cambia: el saldo vive en DataBridge |
| `deuda.saldada` | Pasa a **pagada** |
| `repactacion.aceptada` | Pasa a **en convenio de pago**, y la cartera del mes siguiente no la reabre |
| `deuda.disputada` | Pasa a **disputada** |
| `deuda.retirada` | Pasa a **retirada** |

Cada evento se verifica con HMAC y se descarta si tiene más de 5 minutos. El
mismo evento dos veces se procesa una. Los eventos no llegan en orden
garantizado, así que un aviso atrasado no reabre una deuda ya pagada. Los avisos
al cliente pasan por su propia bandeja de salida y los reintenta el mismo
`despachar_reenvios`.

Sin `DATABRIDGE_SECRETO_EVENTOS` APOFYX no recibe eventos; sin suscripción del
cliente, los eventos ponen al día la cartera pero no salen a ninguna parte.

---

## Base de datos

21 tablas y 3 vistas. **APOFYX sí guarda deudores y deudas**: es una empresa de
cobranza y sin la cartera no tiene nada que trabajar. Lo que **no existe** es
ninguna tabla de pago ni de transacción; el dinero lo mueve DataBridge y acá solo
llega el aviso.

Los nombres dicen el rol de cada cosa en el negocio. El más importante es
`crm_creditor`: es **la empresa acreedora**, la que tiene deudores y contrata a
APOFYX. Se llamaba `crm_company`, y ese nombre no distinguía nada, porque acá hay
tres empresas en juego: APOFYX, la acreedora y DataBridge.

El archivo `sql/AphofyxDB.sql` trae el esquema, los datos de referencia, cinco
empresas de demostración con sus campañas, y el catálogo del asistente (19
intenciones, 117 patrones, 19 respuestas).

Docker lo ejecuta solo la primera vez, al inicializar el volumen. Si cambias el
script, hace falta `docker compose down -v` para que se vuelva a cargar: un
`restart` no basta.

---

## Estado

| Parte | Estado |
| --- | --- |
| Sitio público y formulario de contacto | Funcionando |
| Base de datos y datos de demostración | Funcionando |
| Entorno Docker | Funcionando |
| Admin de Django | Funcionando |
| Asistente del sitio | Funcionando: motor híbrido, flujo de demo y widget |
| Panel de administración | Funcionando: resumen, clientes, ficha, leads y alta/edición |
| Pruebas | 168 pruebas, 99% de cobertura |

---

## Pruebas

```bash
python manage.py test
```

**168 pruebas, 99% de cobertura.** La lógica de negocio está cubierta al 100%:
el motor del asistente, las vistas del panel, las del sitio y los formularios.

Ninguna prueba llama a la API de Gemini: el respaldo con modelo se simula. Lo que
se verifica no es que el modelo responda bien —eso se probó a mano contra la API
real— sino que el motor lo invoque en el momento correcto y **degrade sin
romperse** cuando la API falla.

Para medir la cobertura:

```bash
python -m coverage run --source=crm,assistant,config --omit="*/migrations/*,*/tests.py" manage.py test
python -m coverage report -m
```

> Django crea una base aparte (`test_apofyx`) y la borra al terminar. El permiso
> para hacerlo lo otorga la Parte 5 de `sql/AphofyxDB.sql`; sin eso, `manage.py
> test` falla al intentar crearla.

---

## Documentación

Todo el caso está en [`docs/APOFYX.md`](docs/APOFYX.md): el modelo de negocio, los
actores, el hallazgo central sobre la brecha de confianza, las métricas, el modelo
de datos, el marco legal chileno y las decisiones de diseño con su justificación.
