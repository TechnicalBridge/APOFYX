# APOFYX — Informe - Documentacion de la empresa

> **Alcance de este repositorio.** Aquí vive **solo APOFYX**: su sitio público, su panel de
> administración de clientes y su asistente conversacional. **APOFYX no procesa pagos.** La
> mensajería al deudor, la conversación sobre su deuda, el código de acceso y el pago los resuelve
> **DataBridge** —el software de la organización **Technical Bridge**— en otro repositorio. Ver §12
> y §13.

| Campo | Valor |
| --- | --- |
| Proyecto | APOFYX — Cobranza digital de carteras masivas |
| Contexto | Capstone · APOFYX como empresa que se integra a DataBridge (Technical Bridge) |
| Versión | 0.3 — rol de Technical Bridge / DataBridge incorporado |
| Fecha | 15 de septiembre de 2026 |
| Stack | Django + MySQL + HTML/CSS/JavaScript, comunicación por JSON |
| Estado | Borrador para revisión · ver §17 |

---

## Tabla de contenidos

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Identidad de la startup](#2-identidad-de-la-startup)
3. [De dónde viene APOFYX: del cobro por llamada al link](#3-de-dónde-viene-apofyx-del-cobro-por-llamada-al-link)
4. [El problema de mercado que APOFYX dice resolver](#4-el-problema-de-mercado-que-apofyx-dice-resolver)
5. [Modelo de negocio B2B2C](#5-modelo-de-negocio-b2b2c)
6. [Actores y personas](#6-actores-y-personas)
7. [El producto: módulos](#7-el-producto-módulos)
8. [Recorrido end-to-end](#8-recorrido-end-to-end)
9. [El asistente del sitio](#9-el-asistente-del-sitio)
10. [La brecha de confianza (hallazgo central)](#10-la-brecha-de-confianza-hallazgo-central)
11. [Métricas y embudo](#11-métricas-y-embudo)
12. [Alcance de este repositorio](#12-alcance-de-este-repositorio)
13. [APOFYX, Technical Bridge y DataBridge](#13-apofyx-technical-bridge-y-databridge)
14. [Arquitectura técnica y modelo de datos](#14-arquitectura-técnica-y-modelo-de-datos)
15. [Riesgos, cumplimiento y límites legales](#15-riesgos-cumplimiento-y-límites-legales)
16. [Glosario](#16-glosario)
17. [Decisiones resueltas y abiertas](#17-decisiones-resueltas-y-abiertas)

---

## 1. Resumen ejecutivo

APOFYX es una empresa chilena de **cobranza extrajudicial** para carteras masivas de ticket bajo. No compra deuda, no opera un call center y **no procesa pagos**. Vende software que
contacta al deudor por canales digitales, le responde con un bot y **le entrega un link**.

La promesa comercial es simple y numéricamente cierta: **gestionar un deudor cuesta casi cero**. Un
call center cobra por gestión; APOFYX cobra un fijo mensual más un porcentaje de lo recuperado. Para
un gimnasio al que le deben $34.900, ninguna llamada humana se paga sola. Un mensaje automático sí.

El problema aparece al otro lado. El deudor recibe, desde **un número que no conoce**, a nombre de
**una marca que nunca contrató**, un mensaje que afirma que debe dinero y **un link para pagarlo**.
Ese objeto es, punto por punto, indistinguible de una estafa por *smishing*. Y cuando el deudor
pregunta si es real, lo que le responde es **un bot** — que no puede probar nada, porque lo único
que puede hacer es afirmar que no es una estafa, exactamente lo que haría una estafa.

Hay un segundo problema, más viejo y menos visible: **APOFYX automatizó el contacto, pero nunca
automatizó el pago**. Viene de una operación donde el cobro se pedía por teléfono y todo lo demás
—el registro, el comprobante, la conciliación— se hacía a mano. Ese lado sigue igual de manual hoy
(§3). El producto termina en el link: no hay portal propio, no hay identidad que respalde el
destino, no hay conciliación. APOFYX ni siquiera sabe si el deudor pagó; se entera semanas después,
cuando el acreedor le manda una planilla.

**Tesis del caso:** APOFYX redujo el costo de contactar a casi cero y descubrió que el cuello de
botella nunca estuvo en el contacto. Estaba en la **confianza**, y la confianza no se automatiza
mandando el mismo link más veces. Por cada deudor que paga, ~1,5 reportan el mensaje como fraude
(§11.2). Por eso hoy, por primera vez, APOFYX está buscando **tecnología para el lado del pago** —
y ahí es donde entra DataBridge (§13).

---

## 2. Identidad de la startup

| Atributo | Definición |
| --- | --- |
| Nombre | **APOFYX** |
| Categoría | Cobranza extrajudicial · operación de gestión de cartera |
| Fundación | 2024, Santiago de Chile |
| Equipo | 9 personas (3 ingeniería, 2 datos, 2 comercial, 1 legal part-time, 1 operaciones) |
| Etapa | Pre-seed levantado, buscando seed |
| Mercado | Chile. Moneda CLP |
| Sitio | apofyx.cl |
| Tagline | *"Recupera tu cartera sin call center."* |

### 2.1 Cómo se posiciona

APOFYX **no** se presenta como una empresa de cobranza tradicional. Se presenta como
**infraestructura de contacto**: software que la empresa acreedora enchufa a su cartera morosa. La
diferencia importa comercialmente —le vende a un gerente de finanzas o de TI, no a un jefe de
cobranza— y es justamente la raíz del problema de confianza: **la marca que cobra no es la marca que
vendió**.

### 2.2 Lo que APOFYX explícitamente NO hace

- **No procesa pagos.** No aloja pasarelas, no recibe dinero, no concilia, no emite comprobantes.
  Su producto **termina en el link**. Esta es la frontera más importante de todo el documento.
- **No compra cartera.** Actúa como mandatario de cobranza; la deuda nunca cambia de dueño.
- **No humaniza la IA.** Decisión declarada: el bot se identifica como bot, no tiene nombre de
  persona, no simula empatía. La empresa lo vende como transparencia. En la práctica también es
  cobertura legal, y termina **agravando** la desconfianza (§10.3, causa 4).
- **No hace cobranza judicial.** Pasados los 120 días devuelve el caso al acreedor.
- **No tiene operadores humanos hablando con deudores.** Hay un buzón de escalamiento con SLA
  declarado de 48 horas hábiles, atendido por una sola persona.

---

## 3. De dónde viene APOFYX: del cobro por llamada al link

APOFYX no nació siendo una empresa de tecnología. Nació siendo una operación de cobranza chica y
manual, y ese origen explica casi todo lo que hoy le falta.

### 3.1 Cómo se cobraba antes (2024 – mediados de 2025)

El cobro se solicitaba **por llamada telefónica**. Un ejecutivo marcaba, pedía el pago, y el resto
del proceso se sostenía a pulso:

| Paso | Cómo se hacía | Herramienta |
| --- | --- | --- |
| Recibir la cartera | El acreedor mandaba una planilla por correo | Excel |
| Asignar a quién llamar | Ordenar la planilla a criterio del ejecutivo | Excel |
| Contactar | Llamada telefónica, una por una | Teléfono |
| Registrar la gestión | Anotar a mano el resultado en una columna | Excel |
| Entregar el dato de pago | Dictar la cuenta por teléfono o mandarla por correo | Correo / voz |
| Recibir el comprobante | El deudor mandaba una foto de la transferencia | WhatsApp |
| Confirmar el pago | Revisar a ojo contra la cartola del acreedor | Cartola bancaria |
| Reportar al acreedor | Armar un resumen mensual a mano | Excel |

**Todo era manual, de punta a punta.** Sin sistema, sin base de datos, sin trazabilidad. La
capacidad total de la operación era exactamente igual a cuántas llamadas alcanzaban a hacer al día.

### 3.2 Qué automatizó APOFYX (mediados de 2025)

Al llegar la tecnología, la empresa atacó lo que más dolía: **el contacto**. Dejó de marcar
teléfonos y pasó a mandar mensajes masivos por WhatsApp y SMS, con plantillas y un orden por
antigüedad de la mora. El costo por gestión se desplomó de ~$1.900 a ~$18 y la cobertura pasó del
22% de la cartera al 100%.

De ahí salió el pitch de *"cobranza con IA"* con el que APOFYX sale a vender. **No había IA
detrás**: había una plantilla, una planilla ordenada y un envío masivo (§7.3). Es la distancia
entre lo que se promete y lo que se entrega, y explica por qué el deudor recibe algo tan pobre.

### 3.3 Qué NO automatizó: el pago

Y aquí está el punto ciego. **El lado del pago quedó exactamente igual que en 2024.**

| Etapa | Antes (llamada) | Hoy (IA) |
| --- | --- | --- |
| Contacto | Manual, uno por uno | **Automatizado** |
| Priorización | Criterio del ejecutivo | **Orden fijo: antigüedad y monto** |
| Respuesta al deudor | Ejecutivo al teléfono | **Bot** |
| Entrega del medio de pago | Dictar la cuenta por teléfono | **Un link** |
| Confirmación del pago | Foto por WhatsApp, revisada a ojo | **Igual** |
| Conciliación | A mano contra la cartola | **Igual** |
| Reporte al acreedor | Planilla mensual armada a mano | **Igual** |

De siete etapas, automatizaron tres. Las cuatro que quedaron manuales son **todas las que vienen
después de que el deudor decide pagar**.

El resultado es una empresa asimétrica: **puede contactar a 10.000 personas en una tarde y no sabe
cuántas de ellas pagaron hasta fin de mes.** Cambió el dictado de una cuenta bancaria por un link, y
llamó a eso transformación digital. Es una mejora real de eficiencia en el contacto, pero deja
intacto —y ahora mucho más expuesto por el volumen— el proceso manual de atrás.

### 3.4 Por qué recién ahora busca tecnología para los pagos

Con volumen bajo y llamadas, la conciliación a mano era molesta pero viable: quince pagos al mes se
revisan a ojo. Con volumen alto y mensajes automáticos, el mismo proceso manual se volvió
insostenible, y además dejó al descubierto dos cosas que antes no se veían:

1. **El deudor ya no tiene con quién hablar.** En la llamada, la voz del ejecutivo *era* la prueba
   de legitimidad. El link no prueba nada (§10).
2. **APOFYX perdió la trazabilidad.** El ejecutivo sabía a quién había llamado y qué había
   prometido. El sistema actual sabe quién hizo clic, y nada más (§11.3).

Por eso **es la primera vez que APOFYX sale a buscar una solución tecnológica para el lado del
pago**. No es una optimización: es el reconocimiento de que automatizaron la mitad del proceso y la
mitad que dejaron atrás es la que sostiene la confianza. Esa búsqueda es la que la lleva a Technical
Bridge (§13).

---

## 4. El problema de mercado que APOFYX dice resolver

La cobranza tradicional tiene un piso de costo: alguien humano marca, espera, habla, registra. Ese
costo por gestión efectiva ronda los **$1.500–$2.500 CLP**. Para carteras de ticket alto —créditos
de consumo, automotriz, hipotecario— se justifica sin discusión.

Para el segmento que APOFYX ataca, **no se justifica nunca**:

| Rubro | Ticket moroso típico (CLP) | Margen recuperable | ¿Paga una llamada? |
| --- | --- | --- | --- |
| Gimnasios (cuotas) | $32.900 – $49.900 | bajo | No |
| Institutos y preuniversitarios | $180.000 – $340.000 | medio | Marginalmente |
| Clínicas dentales / veterinarias | $60.000 – $800.000 | medio | A veces |
| ISP regionales | $18.990 – $34.990 | muy bajo | No |
| Gastos comunes | $90.000 – $450.000 | bajo | No |

El resultado real de ese segmento es que **la cartera se castiga sin gestionarse**. No es que la
gestionen mal: no la gestionan. Ese es el hueco que APOFYX ve, y es un hueco real.

**La apuesta:** si el costo marginal de una gestión baja a ~$0, conviene gestionar el 100% de la
cartera incluso con una tasa de éxito baja. Volumen en vez de efectividad.

La apuesta es aritméticamente sólida y **se rompe por un supuesto no declarado**: que un mensaje
automático y un mensaje humano tienen la misma credibilidad ante quien lo recibe. No la tienen — y
la propia historia de APOFYX lo demuestra, porque cuando cobraba por llamada ese supuesto ni
siquiera hacía falta (§3.4).

---

## 5. Modelo de negocio B2B2C

```
   APOFYX  ──────────►  EMPRESA ACREEDORA  ──────────►  DEUDOR
     (B)     software          (B)            su cliente   (C)
                               moroso
      │                                                     │
      └──────────────── contacta directamente ──────────────┘
                   (a nombre del acreedor, pero desde
                        la identidad de APOFYX)
```

El B2B2C es literal: APOFYX le vende a la empresa, pero **quien recibe el producto es el cliente de
la empresa**. APOFYX nunca eligió a ese usuario final, y ese usuario final nunca eligió a APOFYX.
Toda la fricción del caso vive en esa flecha de abajo.

### 5.1 Ingresos

| Línea | Estructura | Notas |
| --- | --- | --- |
| Suscripción | 8 – 45 UF/mes según tramo de cartera | Plataforma, panel y soporte B2B |
| Éxito (*success fee*) | 4% – 9% de lo recuperado | Escala con la antigüedad de la mora |
| Onboarding | 15 UF por única vez | Normalización de cartera e integración |
| Canales | Traspasado a costo | WhatsApp por conversación, SMS por unidad |

Tramos de *success fee*: mora 1–30 días → 4%; 31–90 → 7%; 91–120 → 9%.

> **Consecuencia directa de §2.2 y §3.3:** como APOFYX no procesa pagos y concilia a mano, **no
> puede calcular su propia comisión**. Depende de que el acreedor le informe cuánto recuperó. La
> factura de APOFYX se construye sobre un dato que APOFYX no controla ni puede auditar. Ver §11.3.

### 5.2 Contrato y responsabilidad

La empresa acreedora firma un **mandato de cobranza extrajudicial** y un **acuerdo de tratamiento de
datos** en el que declara tener base legal para entregar los datos del deudor. APOFYX opera como
encargado de tratamiento.

> **Punto crítico:** el mandato autoriza a APOFYX a cobrar. **No le transfiere la confianza** que el
> deudor tenía con el acreedor. Legalmente APOFYX puede contactar; socialmente llega como un
> desconocido. El contrato resuelve lo primero y es ciego a lo segundo.

### 5.3 Unit economics declarados (cartera de 10.000 deudores / mes)

| Concepto | Monto (CLP) |
| --- | --- |
| Ingreso suscripción | 1.350.000 |
| Ingreso success fee (§11.3) | 944.622 |
| Costo canales (WhatsApp + SMS) | −486.000 |
| Costo infraestructura + LLM | −180.000 |
| **Margen bruto por cliente/mes** | **≈ 1.628.622** |

El número cierra. Lo que no muestra es el pasivo que se acumula del otro lado: ~284 reportes de
fraude al mes contra la identidad de envío, que es un activo que se degrada con el uso (§15.3).

---

## 6. Actores y personas

### 6.1 Empresas acreedoras — los clientes de APOFYX

Son **lo único que administra el panel de este repositorio** (§12).

| Empresa | Rubro | Cartera en gestión | Ticket moroso medio | Plan |
| --- | --- | --- | --- | --- |
| **Vitalis Gym** | 14 gimnasios, RM y Valparaíso | 6.200 deudores | $41.300 | Escala |
| **Instituto Andes** | Instituto profesional, 4.200 alumnos | 980 deudores | $268.000 | Pro |
| **Clínica Dental Sonrisa Norte** | 9 sucursales | 1.450 deudores | $184.000 | Pro |
| **NetSur ISP** | Fibra regional, 22.000 clientes | 1.100 deudores | $27.400 | Pro |
| **Administradora Torres del Parque** | Gastos comunes, 6 edificios | 270 deudores | $198.000 | Base |

**Quien decide la compra:** gerente de administración y finanzas. **Qué le importa:** recuperar algo
de lo que hoy castiga, sin contratar gente. **Qué NO mira al firmar:** el efecto sobre su propia
marca cuando sus clientes reciban mensajes de un tercero desconocido.

### 6.2 Deudores — usuarios finales, contexto de negocio

No se administran en este repositorio, pero definen el problema.

| Persona | Perfil | Deuda | Actitud ante el link |
| --- | --- | --- | --- |
| **Marcela Ríos**, 34, TENS | Vitalis, 2 cuotas | $65.800 · 38 días | Pagaría, pero primero quiere **verificar**. Busca el teléfono del gimnasio. |
| **Diego Salas**, 22, estudiante | Instituto Andes, arancel | $360.000 · 71 días | Ignora por defecto todo número desconocido. Ni lo abre. |
| **Rosa Miranda**, 61, jubilada | NetSur | $34.990 · 15 días | Le enseñaron a **nunca** hacer clic en un link. Regla absoluta. |
| **Ignacio Fuentes**, 41, contador | Torres del Parque | $412.000 · 95 días | Quiere pagar, pero exige documento tributario y respaldo formal. Nadie se lo da. |

Cubren los cuatro modos de falla: *quiere verificar y no puede*, *no abre*, *no hace clic por
principio*, *necesita formalidad que el sistema no entrega*.

### 6.3 Visitantes de apofyx.cl — usuarios del chatbot

Este es el público del entregable conversacional de §9. Son **tres audiencias distintas**:

| Visitante | Qué busca | Volumen |
| --- | --- | --- |
| **Prospecto B2B** — gerente de finanzas evaluando contratar | Precios, rubros, integración, seguridad de datos | ~25% |
| **Deudor asustado** — recibió un mensaje y googleó "APOFYX" | *"¿esto existe? ¿es real o me están estafando?"* | **~60%** |
| **Otros** — postulantes, prensa, proveedores | Quiénes son, trabajar con ellos | ~15% |

> **Dato incómodo y central:** la mayoría del tráfico del sitio corporativo **no son clientes
> potenciales, son personas verificando si APOFYX es una estafa**. El sitio existe para vender y en
> la práctica funciona como mesa de verificación. El asistente tiene que atender bien a los tres.

### 6.4 Interno APOFYX

- **Camila Vega** — Customer Success. Atiende el buzón de escalamiento y arma a mano la conciliación
  mensual (§3.3). Es **una sola persona**; el SLA de 48 h es nominal.
- **Operador de campañas** — configura cadencias y segmentos. Nunca habla con un deudor.
- **Administrador de plataforma** — usa el panel de §12 para gestionar la cartera de clientes B2B.

---

## 7. El producto: módulos

```
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│  Sitio + Asistente │  │  Panel de admin    │  │  Motor de contacto │
│  apofyx.cl         │  │  (clientes B2B)    │  │  (IA)              │
│                    │  │                    │  │                    │
│ · Landing B2B      │  │ · Empresas         │  │ · Prioriza         │
│ · Planes           │  │ · Contactos        │  │ · Elige canal      │
│ · Chatbot          │  │ · Planes / cartera │  │ · Redacta copy     │
│ · Captura de leads │  │ · Campañas         │  │ · Agenda toques    │
└────────────────────┘  └────────────────────┘  └────────────────────┘
      EN ESTE REPO            EN ESTE REPO         contexto de negocio

                    ┌──────────────────────────────┐
                    │   Bot de cobranza al deudor  │
                    │   · entrega EL LINK          │
                    └──────────────────────────────┘
                          contexto de negocio
                                  │
                                  ▼
                    ╔══════════════════════════════╗
                    ║   PAGO — fuera de APOFYX     ║
                    ║   hoy: manual (§3.3)         ║
                    ║   futuro: DataBridge         ║
                    ╚══════════════════════════════╝
```

### 7.1 Sitio público y asistente — *se construye aquí*

La cara comercial de APOFYX y su mesa de verificación de facto. Ver §9.

### 7.2 Panel de administración — *se construye aquí*

Gestión de la **cartera de clientes B2B**: qué empresas tiene APOFYX, con qué plan, con qué volumen
de cartera entregada, qué campañas corren y cómo rinden **hasta el clic**. Ver §12.2.

### 7.3 Motor de contacto: qué hay de verdad debajo

> **Corrección importante respecto de versiones anteriores de este documento.**
> Una versión previa describía aquí un motor con modelo de propensión, un LLM que
> redactaba los mensajes y un clasificador de intención. **Eso era incorrecto y
> contradecía §13.6.** APOFYX no tiene inteligencia artificial de ningún tipo.

**APOFYX es una operación, no una empresa de tecnología.** Lo que tiene es:

| Tarea | Cómo la resuelve | ¿Es IA? |
| --- | --- | --- |
| Ordenar a quién contactar primero | Criterios fijos: antigüedad de la mora, monto, canal disponible | **No** |
| Elegir canal y horario | Reglas operativas y la ventana horaria que exige la ley | **No** |
| Redactar el mensaje | Plantillas escritas por personas y aprobadas por el acreedor | **No** |
| Enviar a toda la cartera | Envío masivo con las plantillas y los datos de cada deudor | **No** |
| Medir entregas, aperturas y clics | Los reportes que devuelven los proveedores de canal | **No** |
| Reportar al acreedor | Panel y planilla mensual | **No** |

Nada de eso es inteligencia artificial: es **automatización de oficina aplicada a
escala**. Reemplaza el trabajo de marcar teléfonos, no el de razonar.

> **De dónde sale entonces la IA.** La aporta **DataBridge**, el software de
> Technical Bridge: el agente conversacional que habla con el deudor sobre su
> deuda, el asistente que orienta en el sitio de APOFYX, y el gestor de pagos.
> Ver §13.2. APOFYX opera; DataBridge razona y cobra.

Esa distinción importa para el caso: cuando APOFYX se vendía como *"cobranza con
IA"*, lo que en realidad había detrás era una plantilla y un envío masivo.

### 7.4 El link — el borde del producto

Lo más importante de esta sección es lo que **no** existe.

APOFYX genera un link de pago hacia el destino que indique el acreedor: su propio portal, un botón
de pago, una transferencia. **APOFYX no aloja ese destino, no lo diseña, no lo firma, no lo
concilia.** Su producto termina exactamente cuando el mensaje sale.

Eso significa que:

- El link apunta a un dominio que **tampoco** es el de APOFYX, y a menudo tampoco es reconocible
  para el deudor.
- No hay nada que acredite que el link es legítimo. Ni identidad, ni contexto, ni comprobante.
- APOFYX **no puede medir** qué pasó después del clic (§11.3).
- Si el deudor pregunta "¿y esta página es segura?", el bot no tiene forma de responder, porque la
  página no es de APOFYX.

Cuando el pitch dice *"cobranza con IA"*, lo que el deudor recibe es **un mensaje automático y un
link pelado**. Ese es el producto completo. Antes, en la etapa de llamadas, ese mismo momento lo
resolvía una persona dictando una cuenta; el proceso era peor en costo y mejor en credibilidad.

---

## 8. Recorrido end-to-end

```
 1. Mandato        La empresa firma y entrega su cartera
       │
 2. Normaliza      APOFYX valida RUT, teléfonos, deduplica
       │
 3. Ordena         Por antigüedad de la mora y monto, con criterios fijos
       │
 4. Campaña        Cadencia: día 1 · día 4 · día 11 · día 25 · día 45
       │
 5. Envío  ──────► WhatsApp / SMS / email  ·  mensaje + LINK
       │
       ├──► el deudor NO abre .......................... 35,5%
       ├──► abre y no hace nada ........................ 54,1%
       ├──► responde al mensaje ──► bot de cobranza .... 10,1%
       │                                │
       │                                └──► el bot entrega el link
       │
 6. Clic ────────►  ╔═══════════════════════════════════╗  ... 7,4%
                    ║  AQUÍ TERMINA APOFYX              ║
                    ║  destino de pago del acreedor     ║
                    ║  · sin identidad verificable      ║
                    ║  · sin conciliación automática    ║
                    ║  · sin trazabilidad para APOFYX   ║
                    ╚═══════════════════════════════════╝
       │
 7. Semanas después: el acreedor manda una planilla con lo recuperado
       │                y Camila la cuadra a mano (§3.3)
       │
 8. APOFYX factura su success fee sobre ese dato
```

Y la rama que el pitch comercial no dibuja:

```
 5'. Envío ──► el deudor sospecha
        ├──► reporta el número como spam/estafa ......... 2,8%
        ├──► pide no ser contactado ..................... 4,2%
        ├──► busca "APOFYX" en Google y entra al sitio
        │    a preguntarle al chatbot si son reales ..... ver §6.3
        ├──► llama al call center DEL ACREEDOR a
        │    preguntar si el mensaje es verdadero ....... 1,5%
        └──► no hace nada y no paga
```

Dos consecuencias que rompen la promesa comercial:

1. **El acreedor contrató a APOFYX para no tener call center, y termina recibiendo llamadas para
   validar los mensajes de APOFYX.**
2. **El sitio corporativo de APOFYX se convierte en su canal de soporte al deudor**, sin haber sido
   diseñado para eso. De ahí la importancia del asistente (§9).

---

## 9. El asistente del sitio

> **De quién es este asistente.** Lo provee **DataBridge**, no APOFYX: es la
> misma tecnología conversacional de Technical Bridge, puesta al servicio del
> sitio de APOFYX para orientar a quien llega (§13.2). APOFYX no construyó ni
> opera inteligencia artificial.
>
> No confundirlo con el **agente que habla con el deudor sobre su deuda**, que
> también es de DataBridge pero vive en el portal del cliente, no acá. El
> asistente de apofyx.cl no conversa sobre deudas de nadie: orienta al visitante
> y captura contactos comerciales.

### 9.1 Qué es

Asistente del sitio público. Su trabajo es **orientar a quien llega a apofyx.cl y resolverle lo que
venía a resolver**, sea cual sea de las tres audiencias de §6.3. Tiene que ser bueno: no un menú
disfrazado de chat, sino algo que efectivamente responda precios, explique la integración, agende
una demo y oriente a quien llegó asustado.

**Sigue sin humanizarse.** Se identifica como asistente automático, no tiene nombre de persona, no
simula empatía ni emociones. Es claro, directo y útil. La diferencia con el bot de cobranza es que
acá **sí tiene información real que entregar**, y por eso sí puede resolver.

### 9.2 Intenciones

**Prospecto B2B**

| Intención | Ejemplo | Qué resuelve |
| --- | --- | --- |
| `que_es_apofyx` | "qué hacen ustedes" | Explicación en una frase + a quién sirve |
| `como_funciona` | "cómo funciona el servicio" | Los 5 pasos de §8, sin jerga |
| `precios_planes` | "cuánto cuesta", "planes" | Explica que no se publican tarifas y deriva al formulario de contacto |
| `rubros_requisitos` | "sirve para un gimnasio" | Rubros atendidos, tamaño mínimo de cartera |
| `integracion_datos` | "cómo les entrego mi cartera" | Formato CSV, campos requeridos, API |
| `seguridad_cumplimiento` | "es legal", "y mis datos" | Marco de §15, rol de encargado de tratamiento |
| `agendar_demo` | "quiero una demo" | **Flujo multi-paso**: pide nombre, empresa, email y tamaño de cartera, y **graba el lead en la BD** |
| `hablar_con_ventas` | "quiero hablar con alguien" | Datos de contacto + registro del lead |

**Deudor que llegó a verificar** — la audiencia mayoritaria

| Intención | Ejemplo | Qué resuelve |
| --- | --- | --- |
| `recibi_mensaje` | "me llegó un mensaje de ustedes" | Explica qué es APOFYX y por qué lo contactaron |
| `es_estafa` | "esto es estafa", "es real?" | Explica cómo verificar **con el acreedor** |
| `no_es_mi_deuda` | "yo no debo nada" | Canal de disputa, registra la consulta |
| `no_me_contacten` | "saquen mi número" | Registra la solicitud de opt-out |
| `quien_les_dio_mis_datos` | "de dónde sacaron mi teléfono" | Explica el mandato del acreedor |

**Transversales**

| Intención | Ejemplo |
| --- | --- |
| `trabaja_con_nosotros` | "buscan gente" |
| `contacto_humano` | "quiero hablar con una persona" |
| `saludo` / `despedida` / `agradecimiento` | — |
| `fallback` | cualquier otra cosa → menú de las 4 rutas principales |

### 9.3 Cómo se implementa — híbrido: reglas primero, LLM de respaldo

**Decisión D4.** El asistente resuelve con reglas lo que puede, y solo cuando no alcanza recurre a
un modelo de lenguaje. Nunca al revés.

```
  Mensaje del visitante
        │
        ▼
  Normalizar  (minúsculas, sin tildes, sin puntuación)
        │
        ▼
  ¿Hay un flujo multi-paso abierto?  ── sí ──► continuarlo (ej. schedule_demo)
        │ no
        ▼
  Matching contra IntentPattern  ──►  puntaje por intención
        │
        ├── puntaje ≥ umbral ──► IntentResponse desde MySQL          [ruta normal]
        │                         · determinista
        │                         · auditable por legal
        │                         · sin costo, sin internet
        │
        └── puntaje < umbral ──► respaldo LLM                        [ruta excepción]
                                  · contexto: planes, rubros y FAQ
                                    leídos de la BD
                                  · system prompt con los límites
                                    de §9.4
                                  · si no hay API key o falla la
                                    llamada → IntentResponse de
                                    `fallback`
```

Todo el conocimiento **vive en MySQL**, editable desde el panel: `Intent`, `IntentPattern`,
`IntentResponse`, y el historial en `Conversation` / `Message` (§14.3). Frontend en JavaScript sin
frameworks, conversando con Django por **JSON**.

**Por qué híbrido y no solo LLM:** las respuestas sobre precios, plazos y tratamiento de datos son
declaraciones comerciales y legales de la empresa. Esas salen de la base de datos, revisadas, y no
se generan. El LLM cubre lo que el catálogo de intenciones no previó — reformulaciones raras,
preguntas mezcladas, lenguaje coloquial — y responde acotado al contexto que se le pasa.

**Configuración del respaldo**

| Aspecto | Definición |
| --- | --- |
| Proveedor | **Google Gemini**, tier gratuito de AI Studio |
| SDK | `google-genai==2.23.0` (ya en `requirements.txt`) |
| Qué requiere | Una `GEMINI_API_KEY` en el `.env`. Nada más: sin descargas, sin GPU, sin servicios que levantar |
| Credenciales | Siempre en el `.env`, nunca en el código ni en el repositorio |
| Degradación | **Sin `GEMINI_API_KEY` el sitio funciona igual**: cae en la respuesta `fallback` de la BD |
| Registro | Cada respuesta se guarda en `Message` marcada con su origen (`rules` / `llm` / `fallback`) |

La degradación no es un detalle: como el asistente es híbrido, **la ausencia del LLM no rompe nada**.
Si la clave falta, si se acaba la cuota o si la llamada falla, el visitante igual recibe una
respuesta — la del catálogo de reglas. El LLM mejora la cobertura; no la sostiene.

La fila de **registro** importa para la defensa: como cada respuesta queda marcada con su origen, el
panel puede mostrar **qué porcentaje resolvió el catálogo de reglas y qué porcentaje necesitó el
modelo**. Es una métrica honesta de qué tan completo está ese catálogo.

> Los identificadores exactos de modelo hay que confirmarlos al implementar: el catálogo del tier
> gratuito de AI Studio cambia seguido. El identificador se lee desde el `.env`, así que actualizarlo
> no implica tocar código.

**Por qué Gemini y no DeepSeek** (se evaluó, quedó descartado para el hospedado):

| Criterio | Gemini | DeepSeek |
| --- | --- | --- |
| Costo de la API hospedada | Tier gratuito real, sin tarjeta | **De pago por uso**: barato, pero hay que cargar saldo |
| Ajuste a la tarea | Modelos Flash, pensados para respuestas cortas | Su modelo insignia es de **razonamiento**: cadena larga antes de responder, lento y verboso para un FAQ de sitio |
| Puesta en marcha | Una API key y listo | Cuenta, carga de saldo y gestión de consumo |

Se evaluó también correr un modelo abierto en local (Gemma o Qwen vía Ollama) y se descartó por lo
mismo que DeepSeek: agrega un servicio que instalar, mantener y levantar el día de la defensa. Con
Gemini basta una API key.

**Nota de datos:** el tier gratuito de Gemini puede usar el contenido enviado para mejorar sus
modelos. Es irrelevante en este proyecto —toda la data es sintética y el asistente atiende un sitio
público— pero quedaría registrado como un punto a revisar si alguna vez se tratara data real.

> **Para una demo sin internet**, basta con no cargar la `GEMINI_API_KEY`: el asistente responde solo
> por reglas y el sitio funciona completo. Conviene tener el catálogo de intenciones bien poblado
> justamente para que ese modo no se note.

### 9.4 El límite honesto del asistente

Para el prospecto B2B, el asistente resuelve de verdad: precios, integración, demo agendada.

Para el deudor asustado, resuelve **parcialmente**, y vale la pena escribir por qué:

```
Visitante:  me llegó un whatsapp diciendo que debo plata al gimnasio, es real?

Asistente:  APOFYX es una empresa de cobranza que gestiona carteras por encargo
            de otras empresas. Si el mensaje menciona a Vitalis Gym, es porque
            Vitalis nos encargó la gestión.
            Para confirmarlo con seguridad, comuníquese directamente con Vitalis
            Gym por los canales que usted ya conoce: su sucursal, su app o el
            teléfono que aparece en su contrato.
            No le pedimos que confíe en nosotros. Le pedimos que verifique
            con ellos.
```

Esa respuesta es **correcta y sigue sin resolver el negocio**: es honesta, protege al visitante y
derrumba la premisa comercial completa. APOFYX se vendió como *"no necesitas call center"*, y su
propio asistente termina mandando a la gente a llamar al call center del cliente.

**Ese es el caso, en cuatro líneas de chat.**

---

## 10. La brecha de confianza (hallazgo central)

### 10.1 Enunciado

> El deudor no puede distinguir un cobro legítimo de APOFYX de un intento de fraude, **porque no
> existe ninguna diferencia observable entre ambos desde su teléfono**.

No es un problema de redacción del mensaje. Es estructural: APOFYX construyó un canal que tiene
todas las propiedades formales de un ataque de *smishing* y ninguna propiedad de verificación.

### 10.2 Comparación lado a lado

| Señal que ve el deudor | Mensaje de APOFYX | Smishing real |
| --- | --- | --- |
| Remitente | Número desconocido | Número desconocido |
| Marca que lo firma | Desconocida para él (APOFYX) | Desconocida o suplantada |
| Menciona una deuda | Sí | Sí |
| Urgencia | "antes del 30/09" | "antes de 24 horas" |
| Link | Dominio corto, no es el del acreedor | Dominio corto |
| Destino del link | No controlado por quien lo manda | No controlado |
| Se puede verificar fuera del canal | **No** | No |
| Hay un humano al otro lado | **No** (buzón, 48 h) | No |

**Las ocho señales coinciden.** No hay ninguna en la que el mensaje legítimo se distinga del
fraudulento. Un deudor que desconfía no está siendo paranoico: está leyendo bien la evidencia.

### 10.3 Las cinco causas raíz

1. **Cesión de marca sin cesión de confianza.** El deudor tiene relación con Vitalis. APOFYX es un
   tercero que apareció. El mandato es legal, pero la confianza no se transfiere por contrato.
2. **El producto termina en el link.** APOFYX no controla el destino, así que no puede dotarlo de
   identidad, respaldo ni comprobante. Vende "cobranza con IA" y entrega **un link pelado**.
3. **Paradoja de la prueba de legitimidad.** Para demostrar que conoce la deuda, el mensaje tendría
   que mostrar datos personales. Pero mostrarlos (a) es justo lo que haría un fraude que compró una
   base filtrada, y (b) es un incidente de datos si el número fue reasignado. **No hay jugada buena.**
4. **La IA como agravante, no como atenuante.** Cuando el deudor detecta que habla con un bot, la
   percepción de riesgo **sube**. Un bot pidiendo dinero se lee como automatización de una estafa,
   no como eficiencia. No humanizar es éticamente correcto y comercialmente costoso; APOFYX nunca
   midió ese costo.
5. **Cero verificación *out-of-band*.** No existe camino por el cual el deudor confirme la deuda
   desde un canal que **ya** confía. Todo vive dentro del canal sospechoso, y **un canal no puede
   certificarse a sí mismo**.

### 10.4 Lo que se perdió al dejar la llamada

Vale la pena notar que la etapa manual de §3.1 **resolvía la confianza sin proponérselo**:

| | Llamada (2024) | Link (hoy) |
| --- | --- | --- |
| Prueba de que hay alguien real | La voz | Ninguna |
| Se puede preguntar y repreguntar | Sí | No |
| Se puede pedir que devuelvan el llamado | Sí | No |
| Costo por gestión | $1.900 | $18 |
| Cobertura | 22% | 100% |

APOFYX cambió credibilidad por escala, sin registrar que estaba haciendo ese canje. La llamada era
cara, lenta y no escalaba — y era **verificable**. El link es barato, instantáneo, infinito — y no
prueba nada.

### 10.5 La asimetría que define el caso

```
   Para APOFYX el link es       │   Para el deudor el link es
   ───────────────────────────  │  ───────────────────────────
   el final del embudo          │   el comienzo del riesgo
   la conversión                │   una decisión irreversible
   un endpoint                  │   plata que puede perder
   barato de mandar             │   caro de equivocarse
```

APOFYX optimiza el costo de **enviar**. El deudor evalúa el costo de **equivocarse**. Son dos
funciones distintas, y la empresa solo instrumentó la suya.

### 10.6 Por qué "más toques" empeora todo

La respuesta instintiva a una conversión de 1,9% es subir la cadencia. Es contraproducente:

- Más mensajes desde un número no reconocido → **más reportes de spam** → degradación de la
  reputación del remitente → **menor tasa de entrega** de los mensajes siguientes.
- Más insistencia con el mismo argumento no resuelto refuerza la lectura de fraude, porque **la
  insistencia es en sí misma un patrón de fraude**.
- El techo no es de alcance. Es de credibilidad. **Repetir un mensaje que no se cree no lo vuelve
  creíble.**

### 10.7 Hacia dónde apunta el caso

Si el problema es que la confianza no vive en el canal, la solución no es un mejor bot ni un mejor
copy: es **mover el pago a un lugar con identidad verificable y devolverle trazabilidad a APOFYX**.
APOFYX no puede construir eso —no es su negocio ni su competencia, y nunca tuvo tecnología de pagos
(§3)— así que lo **integra**. Ese es el puente hacia DataBridge (§13).

---

## 11. Métricas y embudo

### 11.1 Lo que APOFYX SÍ puede medir — campaña de 30 días, 10.000 deudores

| Etapa | Volumen | % de cartera | % del paso anterior |
| --- | --- | --- | --- |
| Deudores en campaña | 10.000 | 100% | — |
| Mensajes enviados (3 toques prom.) | 26.400 | — | — |
| Mensajes entregados | 24.100 | — | 91,3% |
| Deudores que abrieron ≥1 mensaje | 6.450 | 64,5% | 64,5% |
| Deudores que respondieron al bot | 1.010 | 10,1% | 15,7% |
| **Clic en el link** | **738** | **7,4%** | **11,4%** |

**El embudo de APOFYX termina en el clic.** Más allá no tiene instrumentación.

### 11.2 El otro embudo — el que no está en el pitch deck

| Evento | Volumen | % de cartera |
| --- | --- | --- |
| Reportes de spam / fraude contra el remitente | 284 | 2,8% |
| Solicitudes de opt-out ("no me contacten") | 417 | 4,2% |
| Disputas ("no es mi deuda") | 193 | 1,9% |
| Llamadas al call center **del acreedor** para validar | 152 | 1,5% |
| Visitas al sitio de APOFYX para verificar si es estafa | 1.240 | 12,4% |
| Escalamientos al buzón humano | 331 | 3,3% |
| Escalamientos respondidos dentro del SLA de 48 h | 96 | 29% del total |

> **El número que define el caso:**
> **189 pagos vs. 284 reportes de fraude.**
> Por cada persona que paga, 1,5 concluyen que es una estafa.
> APOFYX está produciendo más desconfianza que recaudación.

### 11.3 El punto ciego

Los 189 pagos **no los midió APOFYX**. Llegaron en una planilla que el acreedor envía a fin de mes y
que se cuadra a mano (§3.3).

| Consecuencia | Detalle |
| --- | --- |
| Rezago | Hasta 30 días para saber si una campaña funcionó |
| Sin trazabilidad | No se sabe **qué** deudor pagó, solo el total. No se puede cerrar el ciclo |
| Sin atribución | Imposible distinguir un pago causado por la campaña de uno espontáneo |
| Facturación a ciegas | El success fee se calcula sobre un número que APOFYX no puede auditar (§5.1) |
| Sin aprendizaje | **Nada se corrige con el resultado real**, porque el resultado real nunca vuelve. Se repiten los mismos criterios mes a mes, sin saber si sirven |

Esa última fila es la más grave: **APOFYX no aprende de si acertó o no.** Mide clics, que es lo
único que ve, y los clics no son plata. Aquí es donde se nota que la "IA" del pitch no existe: ni
siquiera hay un mecanismo capaz de corregirse con el resultado.

**Recuperado reportado:** 189 × $71.400 = **$13.494.600 CLP** · **success fee 7%: $944.622**.

### 11.4 Conversión de un clic a un pago

De 738 clics, 189 pagos: **25,6%**. Dicho de otro modo, **el 74% de quienes ya superaron la sospecha
inicial y hicieron clic, igual no pagaron.** Y APOFYX no tiene forma de saber por qué, porque lo que
pasó después del clic ocurrió en una página que no es suya.

### 11.5 Comparación con el modelo de llamadas que APOFYX abandonó

| Indicador | APOFYX hoy | Cobranza por llamada (§3.1) |
| --- | --- | --- |
| Costo por gestión | ≈ $18 | ≈ $1.900 |
| Cobertura de la cartera | 100% | 22% |
| Tasa de recuperación | 1,9% | 6,8% |
| Trazabilidad del resultado | **nula** | completa |
| Escalabilidad | ilimitada | tope duro |
| Daño reputacional al acreedor | **alto** | bajo |

Leído con honestidad: APOFYX **no es mejor**, es **más barato, más escalable y menos efectivo**, y
externaliza un costo —reputación del acreedor y desconfianza del deudor— que no aparece en su propia
facturación.

---

## 12. Alcance de este repositorio

**Solo APOFYX.** Nada de pagos y nada de lo que corre dentro de DataBridge.

> **Actualizado el 19-09-2026.** Este repositorio ahora **sí recibe y guarda la cartera** de sus
> clientes: deudores, deudas y cargos, en las apps `cartera` e `integracion` (§12.5). Es lo que
> corresponde a una empresa de cobranza —sin la cartera no tiene qué cobrar— y es lo que su propio
> §13.6 le asigna. Lo que sigue fuera, y no va a entrar, es todo lo que toca el dinero.

### 12.1 Sitio público — apofyx.cl

- **Landing comercial B2B**: propuesta de valor, a quién sirve, cómo funciona, resultados.
- **Rubros atendidos**, leídos desde la base de datos, no escritos en el HTML.
- **Consola de campaña** en la portada: el embudo real de una campaña, de enviados a clics.
- **Formulario de contacto** que graba un lead real en MySQL.
- **Asistente conversacional** embebido en todo el sitio (§9).

### 12.2 Panel de administración

Acceso con login. Lo único que administra: **los clientes que APOFYX tiene**.

- **Listado de empresas cliente** con búsqueda, filtros por rubro y estado, y paginación.
- **Ficha de empresa**: datos societarios, contactos, fecha de alta, estado, volumen de cartera
  entregada, campañas y rendimiento **hasta el clic**.
- **Alta y edición** de empresas cliente, con normalización del RUT al guardar.
- **Baja** de una empresa mediante cambio de estado, no borrado: una empresa arrastra
  cartera, campañas y métricas, y eliminarla se llevaría el histórico por delante.
- **Alta, edición y eliminación** de contactos. Ahí sí se borra de verdad, porque un
  contacto no arrastra histórico.
- **Leads** entrantes desde el formulario y desde el asistente.
- **Conversaciones del asistente**, para revisar qué pregunta la gente.
- **Resumen**: nº de clientes, cartera total en gestión y distribución por rubro.

### 12.3 Fuera del alcance

- **Pagos, pasarelas, conciliación, comprobantes.** No es de APOFYX. **No existe ninguna tabla de
  pago ni de transacción en esta base, y esa frontera se mantiene**: el dinero lo mueve DataBridge
  y a APOFYX le llega el aviso.
- Envío real por WhatsApp, SMS o correo.
- El bot de cobranza al deudor (es contexto de negocio, no entregable).
- **Todo lo de DataBridge** (§13.7): mensajería por WhatsApp y Gmail, LLM conversacional sobre la
  deuda, código de acceso, portal sin login y pagos. Vive en su propio repositorio.

### 12.4 Recepción de cartera — *se construye aquí*

El acreedor entrega su cartera morosa por `POST /api/v1/carteras`, en el formato **Cartera v1**
([contrato](../../TB_web/docs/integracion/README.md)). El mismo formato con que APOFYX se la pasa
después a DataBridge: un solo contrato para toda la cadena.

- **`integracion`** autentica con una clave de API por acreedor —de la que solo se guarda la
  huella— y valida lo que el esquema JSON no puede: dígito verificador del RUT, cargos
  efectivamente vencidos, ids repetidos dentro del lote y **el límite de 120 días de §2.2**.
- **`cartera`** guarda deudores, deudas y cargos. Un deudor existe una sola vez por RUT aunque
  deba a varios acreedores.
- **Aceptación parcial**: una deuda mal formada se rechaza sola, con su motivo, y las demás
  entran. Un RUT mal escrito no bloquea las otras 4.999.
- **Idempotencia**: el mismo lote dos veces devuelve la misma respuesta; el mismo id con otro
  contenido se rechaza.
- Un **retiro** saca de gestión una deuda que el acreedor cobró por su cuenta. Es lo que evita
  seguir cobrándole a alguien que ya pagó.

### 12.5 Principio rector

El producto se construye **como lo vendería la empresa**: creíble, limpio, sin autocrítica dentro de
la aplicación. El análisis crítico vive en esta documentación. Una demo que se delata a sí misma no
demuestra nada.

---

## 13. APOFYX, Technical Bridge y DataBridge

> **Nada de esta sección se construye en este repositorio.** Se documenta para dejar claro dónde
> termina APOFYX y dónde empieza lo que resuelve su problema. DataBridge vive en su propio
> repositorio y lo desarrolla otra organización.

### 13.1 Quién es quién

Tres nombres que se confunden con facilidad:

| Nombre | Qué es | Rol en el caso |
| --- | --- | --- |
| **APOFYX** | Empresa de cobranza, **puramente operacional** | El cliente. Tiene la cartera y la relación comercial con las empresas afiliadas. No construye tecnología |
| **Technical Bridge** | **La organización** que desarrolla el software | El proveedor |
| **DataBridge** | **El software** que construye Technical Bridge | La infraestructura que APOFYX pasa a usar |

Dicho de otro modo: *Technical Bridge* es quién, *DataBridge* es qué. Cuando en este documento se
habla de funcionalidades —mensajería, código de acceso, pagos— se habla de **DataBridge**.

**Decisión D1:** APOFYX es una **empresa que termina integrándose a DataBridge**. La lógica cierra
sola con §3, §10 y §11.3: APOFYX viene de un proceso manual, automatizó solo el contacto, y el lado
del pago quedó sin resolver. Ahora sale a buscarlo por primera vez.

### 13.2 Qué entrega DataBridge

Cuatro piezas, y ninguna es de APOFYX:

| Pieza | Qué hace |
| --- | --- |
| **Mensajería por WhatsApp y Gmail** | El envío al deudor deja de salir desde la identidad de APOFYX y pasa a salir desde DataBridge, por **dos canales simultáneos** |
| **LLM conversacional sobre la deuda** | El deudor puede **conversar** sobre lo que debe a la empresa afiliada: monto, origen, cuotas, fechas. No es un menú: es un modelo con acceso a los datos reales de esa deuda |
| **Código de acceso** | Un código que llega **por Gmail y por WhatsApp**, y que abre el portal de DataBridge **sin login** |
| **Portal de pagos** | Dentro del portal, el deudor ve el detalle y paga. Sin crear cuenta, sin contraseña |
| **Asistente del sitio de APOFYX** | La misma tecnología conversacional, orientando a quien visita apofyx.cl y derivando al formulario de contacto (§9) |

### 13.3 El código de acceso: por qué es el cambio estructural

Es la pieza que arregla lo que §10 declaró irreparable, y conviene entender exactamente por qué.

```
   MODELO APOFYX                          MODELO DATABRIDGE
   ─────────────────                      ──────────────────
   "Haz clic en este link"                "Entra a databridge.cl
                                           y escribe el código 4F7K2Q"

   El destino lo elige                    El destino lo eliges TÚ
   quien mandó el mensaje                 escribiendo la dirección

   = exactamente lo que                   = exactamente lo que
     hace un phisher                        un phisher NO puede hacer
```

**Un phisher necesita que hagas clic en su link.** Si el mensaje te dice que vayas por tu cuenta a un
sitio que puedes escribir tú mismo, buscar, o verificar antes de entrar, el atacante pierde el
control del destino — que era todo lo que tenía. El código separa *dónde vas* de *quién te escribió*,
y esa separación es la definición misma de verificación *out-of-band* que APOFYX no tenía (§10.3,
causa 5).

A eso se suman dos refuerzos:

1. **Doble canal.** El mismo código llega por WhatsApp **y** por Gmail. Un atacante que tenga tu
   teléfono rara vez tiene también el correo que registraste con la empresa afiliada. La coincidencia
   entre dos canales que la empresa ya tenía en ficha es, en sí misma, una prueba.
2. **El detalle de la deuda no viaja en el mensaje.** Vive dentro del portal. Eso elimina de raíz la
   paradoja de §10.3, causa 3: ya no hay que elegir entre *parecer legítimo* y *exponer datos a un
   número equivocado*.

### 13.4 Sin login: por qué es anonimato y no descuido

No hay registro, no hay contraseña, no hay cuenta que crear.

| Efecto | Por qué importa |
| --- | --- |
| **Menos datos recolectados** | DataBridge no necesita crear un perfil para cobrarle a alguien. Minimización de datos, alineado con el marco de §15.1 |
| **Menos fricción** | El deudor no tiene relación previa con DataBridge; pedirle que recuerde una clave es pedirle que abandone |
| **Más anónimo** | El deudor paga lo que debe sin quedar inscrito en una plataforma de cobranza |

**El costo honesto:** quien tenga el código ve la deuda. Es el mismo riesgo de número reasignado de
§15.2, mitigado —no eliminado— porque el código va a dos canales distintos que la empresa afiliada ya
tenía registrados. Si exigir **ambos** canales para entrar o solo uno es decisión de Technical
Bridge, no de APOFYX.

### 13.5 Qué cambia en las ocho señales de §10.2

Es la comparación que cierra el caso:

| Señal que ve el deudor | Hoy, con APOFYX | Con DataBridge |
| --- | --- | --- |
| Remitente | Número desconocido | Dos canales a la vez, uno de ellos su correo registrado |
| Marca que lo firma | APOFYX, que nunca contrató | DataBridge, con dominio propio y estable |
| Menciona una deuda | Sí | Sí |
| Urgencia | "antes del 30/09" | Igual |
| Link | Dominio corto, ajeno al acreedor | **No hace falta link**: hay un código |
| Destino | No controlado por quien manda | El portal de quien manda el mensaje |
| **Verificable fuera del canal** | **No** | **Sí — entras tú, por tu cuenta** |
| **Hay alguien al otro lado** | **No** (buzón, 48 h) | **Un LLM con los datos reales de la deuda** |

Las dos filas en negrita son las que importan. Eran las dos únicas señales en las que un cobro
legítimo podía haberse distinguido de un fraude, y eran justamente las dos que APOFYX no tenía.

Sobre la última: la diferencia entre la respuesta automática de APOFYX y el LLM de DataBridge **no es de calidad de
modelo**. El bot de APOFYX solo podía *afirmar* que no era una estafa (§9.4). El LLM de DataBridge
puede *mostrar* el detalle de la deuda dentro de un sitio al que el deudor llegó por su cuenta. Y
mostrar datos en un lugar al que llegaste tú es evidencia; mostrarlos en un mensaje que alguien te
mandó, no.

### 13.6 Reparto de responsabilidades

| Función | APOFYX | DataBridge |
| --- | --- | --- |
| Relación comercial con la empresa afiliada | ✅ | — |
| Mandato de cobranza y cartera | ✅ | — |
| Priorización y estrategia de campaña | ✅ | — |
| Envío por WhatsApp y Gmail | — | ✅ |
| Conversación con el deudor sobre su deuda | — | ✅ |
| Asistente conversacional del sitio de APOFYX | — | ✅ |
| Cualquier componente de inteligencia artificial | — | ✅ |
| Código de acceso y portal | — | ✅ |
| Procesamiento del pago | — | ✅ |
| Conciliación y confirmación | — | ✅ |
| Reporte a la empresa afiliada | ✅ | — |

APOFYX conserva lo que sabe hacer —a quién cobrar, cuándo y con qué estrategia— y **entrega el tramo
que nunca supo resolver**: el momento en que el deudor tiene que creerle y pagar. También recupera
por fin lo de §11.3: con la confirmación de pago viniendo de DataBridge, APOFYX deja de enterarse a
fin de mes por una planilla.

### 13.7 Fuera del alcance de este repositorio

Para que no quede ambigüedad, **nada de lo siguiente se construye aquí**:

- La mensajería por WhatsApp y Gmail.
- El LLM conversacional sobre la deuda.
- La generación, el envío y la validación del código de acceso.
- El portal sin login y todo lo relativo a pagos, conciliación y comprobantes.

Lo que **sí** se construye aquí, y que esta sección decía que no: **el lado de APOFYX de la
integración** (§12.4). Recibe la cartera de sus clientes y, más adelante, se la pasará a DataBridge
con el mismo contrato. Lo que corre *dentro* de DataBridge sigue siendo de su repositorio.

Este repositorio construye **el sitio de APOFYX, su panel de clientes y su asistente** (§12). El rol
de DataBridge se documenta porque define el contexto del caso y explica hacia dónde va APOFYX, no
porque sea un entregable.

---

## 14. Arquitectura técnica y modelo de datos

### 14.1 Stack

| Capa | Tecnología |
| --- | --- |
| Backend | **Django 6.1.1** (Python) |
| Base de datos | **MySQL 8.4**, relacional, con claves foráneas reales |
| Frontend | **Bootstrap 5.3.8** (local, sin CDN) + CSS propio + JavaScript sin frameworks |
| Comunicación | **JSON** sobre HTTP (`fetch` del navegador a vistas Django) |
| Plantillas | Django templates para el sitio y el panel |
| Respaldo del asistente | **Google Gemini**, tier gratuito de AI Studio (§9.3) |
| Entorno | **Docker Compose**: MySQL en contenedor, con la base poblada al arrancar (§14.6) |
| Idioma del código | **Inglés** en modelos, campos y rutas; español en documentación e interfaz |

**Principio, según lo pedido:** nada de data falsa hardcodeada en archivos JSON. Planes, clientes,
intenciones del bot y respuestas son **filas en MySQL**, cargadas por *fixtures* o por un comando de
carga inicial, y editables desde el panel.

### 14.2 Prerrequisitos verificados en este equipo (15-09-2026)

| Componente | Estado | Nota |
| --- | --- | --- |
| Python | **3.14.3** ✓ | Obliga a **Django 6.x**; las series 5.x no soportan 3.14 |
| Django | no instalado | Última disponible: **6.1.1** → fijada en `requirements.txt` |
| `mysqlclient` | **2.2.8 ya instalado** ✓ | Funciona sobre Python 3.14; no hace falta PyMySQL |
| `python-dotenv` | **1.2.1 ya instalado** ✓ | Para sacar credenciales del código |
| `google-genai` | no instalado | Última disponible: **2.23.0** → fijada en `requirements.txt` |
| **Docker 29.6.2** | **funcionando y verificado** ✓ | **Camino elegido.** Levanta MySQL 8.4.11 con la base ya poblada |
| MySQL Server 8.4 | instalado, servicio **detenido** | Alternativa sin Docker. No hizo falta iniciarlo |
| MySQL Workbench 8.0 | instalado | Se conecta al contenedor en `127.0.0.1:3307` |
| XAMPP / MariaDB 10.4.32 | instalado, detenido | **Descartado**: 10.4 es anterior a lo que exige Django 6 |
| Puerto 3306 | libre | Reservado para el MySQL local del equipo |
| Puerto 3307 | **en uso por el contenedor** | Elegido para no chocar con el 3306 |

`requirements.txt` ya está en la raíz del repositorio con las cuatro dependencias fijadas.

> **Por qué Docker y no el MySQL instalado.** El MySQL 8.4 del equipo no tiene servicio registrado ni
> directorio de datos inicializado, así que ponerlo en marcha exige configuración manual. El
> contenedor da un MySQL 8.4.11 limpio, con la base creada y poblada, en unos 15 segundos y con un
> solo comando — y es reproducible en cualquier otro equipo del equipo de trabajo. El MySQL local
> queda como alternativa, documentada en §14.9.

### 14.3 Modelo de datos

**Decisión D12:** modelos, campos, rutas y nombres de código **en inglés**. La documentación, los
textos de la interfaz y los datos siguen en español.

**Script SQL** — el modelo fisico completo vive en un solo archivo: **`sql/AphofyxDB.sql`**.

| Parte | Contenido |
| --- | --- |
| 1 — DDL | Base de datos, **12 tablas**, 13 claves foraneas, 20 CHECK, 13 UNIQUE y **3 vistas** |
| 2 — DML | Datos de referencia que la aplicacion necesita: 6 rubros y 3 planes |
| 3 — DML | Datos de demostracion: los 5 clientes de §6.1 con contactos, carteras, campanas y metricas |
| 4 — DML | Catalogo del asistente: **19 intenciones, 116 patrones y 19 respuestas** (§9.2) |
| 5 | Permisos para las pruebas |
| 6 | Consultas de verificacion que imprimen el inventario, el embudo y el catalogo |

**Estado: verificado ejecutandose.** El archivo se corrio contra un **MySQL 8.4.11** limpio en un
contenedor desechable. Resultado: se aplica sin errores, las 3 vistas devuelven lo esperado, las
metricas reproducen exactamente el embudo de §11.1, y las 6 restricciones que se probaron rechazan
correctamente los datos invalidos. El motor de coincidencias tambien se probo: nueve frases de
ejemplo caen en la intencion correcta, y una frase sin sentido cae en `fallback`.

> **Una trampa que costo encontrar.** El cliente que usa la imagen de Docker para cargar los
> scripts de inicializacion no recibe `--default-character-set`, e interpretaba el archivo como
> latin1: `Clínica` se guardaba como `ClÃ­nica`. Por eso el script empieza con **`SET NAMES utf8mb4;`**
> — asi la codificacion no depende de como se invoque el archivo, y funciona igual desde Docker,
> desde la linea de comandos o desde Workbench.

**Re-ejecucion.** Los `INSERT` son idempotentes: repetirlos no duplica nada. Los `CREATE TABLE` no
lo son a proposito — si las tablas existen el script se detiene con `ERROR 1050`, para que un cambio
de esquema no pase inadvertido. Para reconstruir desde cero hay que descomentar el bloque de
reinicio del propio archivo; asi tambien se verifico, corriendolo dos veces seguidas sin errores.

> **Fuente de verdad.** El DDL está escrito con las convenciones de nombres de Django
> (`<app>_<modelo>`, `id` BIGINT, FK `<campo>_id`), de modo que los modelos que se escriban después
> produzcan este mismo esquema. En ejecución, **las migraciones de Django mandan**; el DDL es el
> modelo físico para el informe y para levantar la base a mano. Hay que mantenerlos alineados: si
> divergen, gana la migración.
>
> Las tablas `auth_user`, `django_session` y `django_migrations` **no** están en el DDL. Las crea
> `python manage.py migrate` y no deben escribirse a mano.

```
  Industry ──┐
             ├──< Creditor >──┬──< CreditorContact
             │                │
             │                ├──< PortfolioHandover
             │                │
             │                └──< Campaign >──< CampaignFunnelSnapshot
             │
             └──< Lead ──> Creditor (opcional, si convierte)

  Intent ──< IntentPattern
     │
     └──< IntentResponse

  Conversation ──< Message >── Intent (detectada)

  User (Django) ── administradores del panel
```

**Los nombres dicen el rol, no la forma.** El caso más importante es `Creditor`:
antes se llamaba `Company`, y ese nombre no distinguía nada — en este dominio hay
tres empresas en juego (APOFYX, la acreedora y DataBridge) y el nombre tiene que
decir cuál es. Lo mismo con `PortfolioHandover`, que es una *entrega* de cartera
con fecha, y `CampaignFunnelSnapshot`, que es una *foto* del embudo completo en un
momento, no un indicador suelto.

**Entidades principales**

| Modelo | Qué es | Campos centrales |
| --- | --- | --- |
| `Industry` | Rubro atendido | `name`, `slug`, `description`, `is_active` |
| `Creditor` | **La empresa acreedora**: tiene deudores y contrata a APOFYX | `legal_name`, `trade_name`, `tax_id`, `industry` FK, `status`, `client_since`, `commune`, `region`, `website`, `internal_notes` |
| `CreditorContact` | Persona de contacto en la acreedora | `creditor` FK, `full_name`, `job_title`, `email`, `phone`, `is_primary` |
| `PortfolioHandover` | **Una entrega de cartera**: lo que el acreedor pasa a gestión en un mes, por tramo de mora | `creditor` FK, `period_month`, `overdue_bracket`, `debtor_count`, `average_debt_clp`, `received_at` |
| `Campaign` | Campaña de contacto sobre esa cartera | `creditor` FK, `name`, `starts_on`, `ends_on`, `status`, `channels`, `contact_attempts` |
| `CampaignFunnelSnapshot` | **Una foto del embudo** en una fecha de corte | `campaign` FK, `measured_on`, `messages_sent`, `messages_delivered`, `messages_opened`, `replies_received`, `link_clicks`, `fraud_reports`, `optout_requests`, `debt_disputes` |
| `Lead` | Contacto comercial entrante | `full_name`, `job_title`, `company_name`, `email`, `estimated_debtor_count`, `estimated_overdue_clp`, `current_collection_method`, `source`, `status`, `inquiry_message`, `conversation` FK, `converted_creditor` FK |
| `Intent` | Intención que el asistente reconoce | `slug`, `name`, `audience`, `tiebreak_priority`, `is_active` |
| `IntentPattern` | Frase que dispara una intención | `intent` FK, `pattern_text`, `match_weight` |
| `IntentResponse` | Respuesta aprobada | `intent` FK, `response_text`, `display_order`, `suggested_action` |
| `Conversation` | Sesión de chat anónima | `session_key`, `inferred_audience`, `is_resolved` |
| `Message` | Un turno de la conversación | `conversation` FK, `speaker`, `message_text`, `intent` FK, `match_confidence`, `answer_engine`, `response_time_ms` |

**Tres campos que conviene entender:**

- **`Lead.converted_creditor`** — si el lead termina siendo cliente, apunta al
  acreedor que se creó. Se llama así y no `creditor` porque no es "el acreedor del
  lead": es el que nació de él.
- **`PortfolioHandover.average_debt_clp`** — deuda promedio del tramo, en pesos.
  Al agregarla hay que **ponderar por `debtor_count`**; el promedio simple de los
  tres tramos da un número falso.
- **`Message.answer_engine`** — qué motor resolvió la respuesta: `rules`, `llm` o
  `fallback`. Es la métrica que dice si el catálogo de intenciones está completo.

**Dónde cae el límite entre inglés y español.** Los nombres de tablas, columnas y
modelos son ingleses, y la documentación y la interfaz son españolas; eso es D12 y
no tiene matices. El caso que sí los tiene son los valores guardados en los campos
con opciones, porque un valor es a la vez dato y parte del código:

- Los que representan un **estado interno del sistema** van en inglés, como el
  resto de los identificadores: `status` (`active`, `paused`…), `source`
  (`form`, `assistant`), `answer_engine` (`rules`, `llm`, `fallback`),
  `speaker` (`visitor`, `assistant`) y `audience` (`prospect`, `debtor`,
  `general`). Nadie los lee salvo el código.
- El único que guarda **lo que una persona declara sobre su propia operación**
  va en español: `Lead.current_collection_method` (`nadie`, `llamadas`,
  `mensajes`, `externo`, `mixto`). No es un estado que el sistema asigne, es la
  respuesta que el visitante eligió en el formulario, y traducirla sólo
  agregaría una capa de traducción entre lo que se preguntó y lo que se guardó.
- `PortfolioHandover.overdue_bracket` no participa de la discusión: sus valores
  son rangos (`1-30`, `31-90`, `91-120`), que no tienen idioma.

Está anotado en `Lead.CollectionMethod` y en el `CHECK` del DDL, porque es
exactamente el tipo de cosa que un renombrado masivo "corrige" por error.

Nótese que **no hay ningún modelo de deudor, deuda, pago ni transacción**. Es deliberado y es la
traducción a esquema del §2.2: APOFYX no toca pagos.

### 14.4 Endpoints JSON previstos

| Método | Ruta | Uso |
| --- | --- | --- |
| `POST` | `/api/chat/` | Mensaje del visitante → intención + respuesta |
| `POST` | `/api/leads/` | Alta de lead desde formulario o asistente |
| `GET` | `/api/plans/` | Planes para render dinámico de la landing |
| `GET` | `/api/admin/companies/` | Listado paginado y filtrable para el panel |
| `GET` | `/api/admin/companies/<id>/` | Ficha completa de un cliente |
| `GET` | `/api/admin/summary/` | Tarjetas del resumen del panel |

### 14.5 Acceso al panel y estado de lo construido

**Verificado funcionando** el 16-09-2026, iniciando sesión de verdad y no solo
comprobando que las rutas respondan:

| Pieza | Estado |
| --- | --- |
| Sitio público y formulario | Funcionando; los leads quedan en MySQL |
| Asistente del sitio | Motor híbrido, flujo de demo y widget. 86,7% resuelto por reglas |
| Panel: resumen | KPIs, embudo acumulado, cobertura del asistente y últimos leads |
| Panel: clientes | Listado con búsqueda, filtros y paginación de 25 |
| Panel: alta y edición | Empresas y contactos, con el RUT normalizado al guardar |
| Panel: ficha | Datos, contactos, cartera por tramo y campañas con su embudo |
| Panel: leads | Listado con filtros por estado y origen |
| Admin de Django | Las 12 tablas registradas con inlines y columnas calculadas |
| Pruebas | **168 pruebas, 99% de cobertura.** Motor, vistas y formularios al 100% |



**Decisión D10:** panel propio con el sistema de autenticación de Django detrás.

- Login con `django.contrib.auth`; las vistas del panel exigen sesión iniciada y permiso de staff.
- El panel de §12.2 es **a medida**: plantillas, filtros y fichas diseñadas, consumiendo los
  endpoints JSON de §14.4.
- El **Django admin nativo queda habilitado en paralelo**, para carga y mantención de datos
  (intenciones del asistente, planes, rubros) sin tener que construir formularios para todo.

### 14.6 Entorno de desarrollo con Docker

Un solo comando levanta la base ya poblada. **Verificado funcionando** el 15-09-2026.

| Archivo | Rol |
| --- | --- |
| `docker-compose.yml` | Orquesta los servicios. `db` activo; `web` bajo el perfil `app` |
| `Dockerfile` | Imagen de la app Django. Instala `mysqlclient`, que se compila |
| `.env.example` | Plantilla de configuración. Se copia a `.env`, que no se versiona |
| `.dockerignore` / `.gitignore` | Qué no entra a la imagen y qué no entra al repositorio |

```bash
cp .env.example .env
docker compose up -d          # levanta solo la base
docker compose down           # detiene, conservando los datos
docker compose down -v        # detiene Y BORRA los datos
```

**Tres decisiones que conviene conocer:**

1. **Puerto 3307, no 3306.** El equipo ya tiene un MySQL 8.4 instalado; publicar en 3306 los haría
   chocar. Desde Workbench o desde Django corriendo fuera de Docker: `127.0.0.1:3307`.
2. **La base se puebla sola.** `sql/AphofyxDB.sql` se monta en `/docker-entrypoint-initdb.d/`, que la
   imagen de MySQL ejecuta **solo la primera vez**, cuando el volumen está vacío. Si se cambia el
   script hay que hacer `docker compose down -v` para que vuelva a cargarse: un `restart` no basta.
3. **El servicio `web` está bajo un perfil.** Todavía no existe el proyecto Django, así que
   `docker compose up` levanta únicamente la base. Cuando exista `manage.py` se activa con
   `docker compose --profile app up -d --build`. Así el entorno es usable hoy sin fingir que la app
   ya está.

**Comprobado:** contenedor `healthy` en ~15 s, las 13 tablas y 3 vistas creadas automáticamente, el
embudo cargado (26.400 enviados / 738 clics / 284 fraudes), acceso correcto con el usuario de
aplicación `apofyx_app` —no solo root— y conexión desde el host por el puerto 3307.

### 14.7 Identidad visual

**Decisión D11 y D13: resueltas.** El logotipo es una **serpiente en teal petróleo
y dorado**. La lámina de referencia está en `docs/marca/ideas-de-iconos.jpg`.

**Paleta, muestreada del logotipo real** (no inventada):

| Rol | Color | De dónde sale |
| --- | --- | --- |
| Teal de marca | `#0f4f58` | Fondo sólido del Apple Touch Icon de la lámina |
| Teal claro | `#1d7d8c` | Derivado, para halos y acentos secundarios |
| Teal oscuro | `#0a3740` | Zona de sombra de la serpiente |
| **Dorado (acento)** | **`#c9a961`** | Promedio de la zona dorada |
| Dorado claro | `#e2c98a` | Brillo, para texto sobre fondo oscuro |
| Dorado oscuro | `#9b7336` | Sombra del dorado |
| Fondo | `#06100f` | Casi negro con la temperatura del teal |

**Decisión de diseño:** en un tema oscuro, el teal `#0f4f58` es demasiado apagado
para funcionar como acento, así que se invirtieron los papeles respecto del
logotipo: el **teal es la familia de superficies y halos**, y el **dorado es el
acento** — botones, enlaces, cifras y etiquetas. Es lo que hace que la marca se
lea sobre negro sin perder el carácter del logotipo.

**Archivos actuales** en `static/brand/`:

| Archivo | Uso | Origen |
| --- | --- | --- |
| `isotipo-color.png` (512×512) | Cabecera y pie, a 36 px | Extraído de la lámina |
| `favicon.ico` (16/32/48) | Pestaña del navegador | Derivado del isotipo |
| `favicon-32.png` | Pestaña, navegadores modernos | Derivado del isotipo |

> **Estos archivos son provisionales.** Se extrajeron de un JPG de presentación
> que contiene las seis piezas juntas sobre un tablero de transparencia simulado.
> Un JPG no tiene canal alfa, así que la transparencia se reconstruyó por umbral
> de saturación: funciona a 36 px, pero al ampliar se notan halos en los brillos y
> el borde no es limpio.
>
> **Para la versión definitiva hacen falta los archivos exportados por separado**,
> idealmente en SVG. Las seis piezas y sus tamaños están especificados en la
> lámina misma y coinciden con lo que necesita el sitio.

### 14.8 Estructura MVT del proyecto

El sitio sigue el patron **MVT** nativo de Django: el **Modelo** consulta MySQL,
la **Vista** arma el contexto, la **Plantilla** lo muestra. No hay SPA ni framework
de frontend; JavaScript se usa solo donde hace falta de verdad (el menu movil y,
mas adelante, el chat).

```
APOFYX/
├── config/              proyecto: settings, urls raiz
├── crm/                 app de clientes B2B
│   ├── models.py        Industry · Plan · Company · CompanyContact
│   │                    AssignedPortfolio · Campaign · CampaignMetric · Lead
│   ├── views.py         portada, contacto, gracias
│   ├── forms.py         LeadForm, que graba en MySQL
│   ├── urls.py          sitio publico
│   └── panel_urls.py    panel interno (requiere sesion)
├── assistant/           app del chatbot
│   ├── models.py        Intent · IntentPattern · IntentResponse
│   │                    Conversation · Message
│   └── urls.py          API JSON en /api/chat/
├── templates/
│   ├── base.html        cabecera, pie y menu responsivo
│   ├── site/            portada y confirmacion
│   └── panel/           panel interno
└── static/
    ├── vendor/bootstrap/ Bootstrap 5.3.8 local, para no depender de internet
    ├── css/main.css      capa de tema: paleta verde y componentes propios
    └── js/animaciones.js aparicion al desplazar, cabecera y conteo de cifras
```

**Adopcion del esquema existente.** Las tablas ya existian, creadas por
`sql/AphofyxDB.sql`. Los modelos son su espejo y se adoptaron con
`manage.py migrate --fake-initial`: Django reconocio las tablas, marco las
migraciones iniciales como aplicadas (`FAKED`) y creo solo las suyas
(`auth_user`, `django_session`, `django_admin_log`, `django_content_type`).
De aqui en adelante mandan las migraciones.

**Interfaz: Bootstrap 5.3.8 con tema oscuro propio.**

Bootstrap aporta la rejilla, los componentes y el modo oscuro nativo
(`data-bs-theme="dark"`). Encima va una capa de tema en `static/css/main.css` que
redefine variables y agrega lo propio. Los archivos estan **descargados en
`static/vendor/bootstrap/`, no en CDN**: asi el sitio funciona sin internet el dia
de la defensa.

| Decision | Detalle |
| --- | --- |
| Tema | Oscuro, casi negro con la temperatura del teal (`#06100f`), no gris puro |
| Acento | Dorado `#c9a961` del logotipo, con `#e2c98a` para texto sobre fondo oscuro |
| Responsivo | Rejilla de Bootstrap; el menu colapsa solo bajo 992 px |
| Tipografia | `clamp()`, crece sola con el ancho y sin saltos |
| Campos | 16 px de tipografia, para que iOS no haga zoom al enfocar |
| Paleta | Variables en `:root`. Cuando exista el logotipo se cambian ahi y listo |
| Accesibilidad | Foco visible, enlace de salto al contenido, `prefers-reduced-motion` |

**Animaciones** (`static/js/animaciones.js`), las tres opcionales:

1. **Aparicion al entrar en pantalla** con `IntersectionObserver`, escalonada en
   las rejillas. Se anima una sola vez y despues se deja de observar el elemento.
2. **Cabecera que se afirma** al bajar la pagina; el listener usa `passive: true`
   para no frenar el desplazamiento.
3. **Conteo ascendente** de la cifra de deudores, con desaceleracion al final.

Si el navegador no soporta `IntersectionObserver`, o si el visitante activo
*reducir movimiento* en su sistema, **todo se muestra de inmediato y sin
animacion**. La pagina nunca depende de que el script corra.

**Verificado funcionando** el 16-09-2026: la portada responde 200 con tema oscuro
activo y las cifras leidas de MySQL (5 empresas, 10.000 deudores, 91,3% de
entrega, 6 rubros); Bootstrap y el CSS propio se sirven desde `static/`; hay 17
bloques animados; el formulario graba leads reales y un envio invalido devuelve
400 mostrando el error en espanol; el panel redirige a login sin sesion.

### 14.9 Puesta en marcha

Dos caminos para tener la base corriendo. El primero es el recomendado y el que está verificado.

#### Camino A — Docker *(recomendado)*

Requiere solo Docker Desktop abierto.

```bash
cp .env.example .env         # en Windows:  copy .env.example .env
docker compose up -d
```

Eso es todo. En unos 15 segundos hay un MySQL 8.4.11 con las 13 tablas, las 3 vistas y los datos de
demostración ya cargados, porque `sql/AphofyxDB.sql` se monta en `/docker-entrypoint-initdb.d/`.

**Credenciales por defecto** (en `.env`, cambiables):

| Dato | Valor |
| --- | --- |
| Host | `127.0.0.1` |
| Puerto | `3307` |
| Base | `apofyx` |
| Usuario de aplicación | `apofyx_app` / `apofyx_pass` |
| Usuario administrador | `root` / `rootpass` |

Desde **MySQL Workbench**: nueva conexión a `127.0.0.1`, puerto `3307`, usuario `apofyx_app`.

**Comandos habituales**

| Comando | Qué hace |
| --- | --- |
| `docker compose up -d` | Levanta la base en segundo plano |
| `docker compose ps` | Estado y puertos |
| `docker compose logs -f db` | Ver el arranque y la carga del script |
| `docker compose down` | Detiene **conservando** los datos |
| `docker compose down -v` | Detiene y **borra** los datos |
| `docker compose exec db mysql -uapofyx_app -papofyx_pass apofyx` | Abrir una consola SQL dentro del contenedor |

#### Camino B — MySQL instalado en el equipo

Sirve si no se quiere usar Docker. Hay que iniciar el servidor MySQL 8.4 —que en este equipo no
tiene servicio registrado ni datos inicializados, así que exige configurarlo— y después:

```sql
-- Como root, una sola vez:
CREATE USER 'apofyx_app'@'localhost' IDENTIFIED BY 'apofyx_pass';
GRANT ALL PRIVILEGES ON apofyx.* TO 'apofyx_app'@'localhost';
FLUSH PRIVILEGES;
```

```bash
mysql -u root -p --default-character-set=utf8mb4 < sql/AphofyxDB.sql
```

Y en el `.env`, apuntar `DB_PORT=3306` en lugar de 3307.

#### Django, cuando exista el proyecto

```bash
python -m venv .venv
.venv\Scripts\activate           # en bash:  source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate         # crea auth_user, django_session, etc.
python manage.py runserver
```

O dentro de Docker, una vez que exista `manage.py`:

```bash
docker compose --profile app up -d --build
```

#### Problemas frecuentes

| Síntoma | Causa y solución |
| --- | --- |
| Cambié `AphofyxDB.sql` y la base sigue igual | El script corre **solo al inicializar** el volumen. Hace falta `docker compose down -v` y volver a levantar; un `restart` no basta |
| `Access denied for user 'root'` recién levantado | El contenedor todavía inicializaba. Esperar a que `docker compose ps` diga `healthy` |
| `port is already allocated` | Otro proceso ocupa el 3307. Cambiar `MYSQL_PORT` en el `.env` |
| `ERROR 1050 ... Table already exists` | Se ejecutó el script sobre una base que ya tenía las tablas. Es el comportamiento buscado (§14.3); para reconstruir, descomentar el bloque de reinicio |
| Acentos o eñes salen mal (`ClÃ­nica`) | El script ya trae `SET NAMES utf8mb4;` en su primera linea, asi que no deberia pasar. Si ocurre al cargar otro archivo, agregar `--default-character-set=utf8mb4` al comando `mysql` |
| Las fechas se ven 3 o 4 horas adelantadas | **No es un error.** El contenedor corre en UTC y Chile está en UTC−3 / UTC−4. Un `created_at` de las 01:45 UTC son las 22:45 en Santiago. Django debe configurarse con `USE_TZ = True` y `TIME_ZONE = 'America/Santiago'`, y así muestra la hora local aunque la base guarde en UTC |
| `mysqlclient` falla al instalarse | En este equipo ya está instalado. En otro, la alternativa sin compilar es `PyMySQL==1.2.0` |

---

## 15. Riesgos, cumplimiento y límites legales

> Las referencias normativas son **orientativas** y deben contrastarse con el texto vigente antes de
> afirmarlas en la defensa.

### 15.1 Marco chileno aplicable

| Norma | Qué regula | Impacto en APOFYX |
| --- | --- | --- |
| **Ley 19.496**, art. 37 y ss. | Cobranza extrajudicial: gastos, conductas prohibidas, ventana horaria | Define qué puede decir el mensaje y a qué hora sale |
| **Ley 19.628** | Protección de la vida privada / datos personales | Base legal para tratar la cartera del acreedor |
| **Ley 21.719** | Nueva Ley de Protección de Datos; crea la Agencia | Endurece el rol de encargado de tratamiento; **verificar entrada en vigencia** |
| **Ley 20.575** | Principio de finalidad en datos económicos | Limita el uso de información de morosidad |

Restricciones operativas derivadas:

- Ventana horaria de contacto y prohibición en domingos y festivos (**verificar texto vigente**).
- Prohibición de contactar a terceros: familiares, vecinos, empleador.
- Prohibición de enviar documentos que **aparenten** ser judiciales o de usar apremios indebidos.
- Derecho del deudor a oponerse al contacto y a que se detenga la gestión.

### 15.2 Riesgo de datos personales

- **Número reasignado.** El teléfono cambió de dueño. APOFYX le manda a un desconocido un mensaje
  con el nombre del acreedor y la mención de una deuda ajena. Es una filtración causada por el
  diseño del canal.
- **Base entregada sin base legal.** El acreedor *declara* tener derecho a ceder los datos. APOFYX
  no lo verifica. La responsabilidad como encargado de tratamiento no desaparece por esa declaración.
- **Conciliación por WhatsApp.** Los comprobantes de pago que los deudores mandan como foto (§3.1)
  contienen datos bancarios y quedan en el teléfono de un ejecutivo, fuera de todo sistema. Es el
  riesgo más concreto y menos atendido de la operación actual.
- **Datos del sitio.** Leads y conversaciones del asistente son datos personales: requieren aviso de
  privacidad, retención definida y borrado.

### 15.3 Riesgo del canal

- **Política de WhatsApp Business:** exige *opt-in* previo y plantillas aprobadas. El deudor dio su
  consentimiento —si lo dio— **al acreedor, no a APOFYX**. Es un flanco directo.
- **Degradación del remitente:** los reportes de spam bajan la calificación del número y pueden
  terminar en bloqueo. El activo principal del canal se consume con el uso.
- **Reputación del dominio:** un dominio reportado entra en listas de bloqueo y filtros antiphishing.

### 15.4 Riesgo para el acreedor

El que APOFYX no le factura y aparece igual: su cliente moroso —que sigue siendo su cliente— recibe
algo que parece una estafa **a nombre suyo**. El daño de marca no lo absorbe APOFYX.

### 15.5 Límites del proyecto

Este proyecto documenta y modela un sistema que se confunde con un fraude. Lo que **no** se hace:

- No se construyen técnicas para **evadir** filtros antispam o antiphishing.
- No se optimiza el mensaje para **parecer más creíble sin serlo**.
- No se usan datos de personas reales ni se envía nada a destinatarios reales: toda la data es
  sintética y cargada por *fixtures*.
- El análisis es **diagnóstico** —por qué falla— y no prescriptivo sobre cómo engañar mejor.

---

## 16. Glosario

| Término | Definición |
| --- | --- |
| **B2B2C** | Se vende a una empresa, pero el producto lo recibe el cliente final de esa empresa |
| **Cartera** | Conjunto de deudas que un acreedor entrega a gestión |
| **Mora temprana** | Deuda vencida entre 1 y 90 días |
| **Castigar cartera** | Darla contablemente por perdida sin gestionarla |
| **Mandato de cobranza** | Contrato por el que el acreedor autoriza a un tercero a cobrar en su nombre |
| **Success fee** | Comisión sobre lo efectivamente recuperado |
| **Toque** | Cada intento individual de contacto dentro de una cadencia |
| **Cadencia** | Secuencia programada de toques (día 1, 4, 11, 25, 45) |
| **Conciliación** | Cuadrar los pagos recibidos contra la cartera, para saber quién pagó qué |
| **Opt-in / opt-out** | Consentimiento previo para ser contactado / solicitud de dejar de serlo |
| **Smishing** | Phishing por SMS o mensajería instantánea |
| **Out-of-band** | Verificación por un canal distinto del que originó el mensaje |
| **Technical Bridge** | **La organización** que desarrolla DataBridge. Es un quién, no un qué (§13.1) |
| **DataBridge** | **El software** de Technical Bridge: mensajería, LLM sobre la deuda, código de acceso y pagos (§13.2) |
| **Código de acceso** | Código que DataBridge envía por Gmail y WhatsApp; abre el portal sin login. El deudor entra escribiendo la dirección, no haciendo clic (§13.3) |
| **Empresa afiliada** | La empresa acreedora vista desde DataBridge: aquella cuya deuda se gestiona |
| **Lead** | Contacto comercial interesado, aún no cliente |
| **Propensión de pago** | Probabilidad estimada de que un deudor pague si se le contacta |

---

## 17. Decisiones resueltas y abiertas

### 17.1 Resueltas

| # | Decisión | Resolución |
| --- | --- | --- |
| **D1** | Relación con Technical Bridge | **Cliente que termina integrándose a DataBridge**, el software de Technical Bridge (§13). **Actualizada el 19-09-2026:** la integración pasó de documentarse a construirse. Aquí vive el lado de APOFYX —recibir la cartera de sus clientes (§12.4)— bajo el contrato común de `TB_web/docs/integracion/` |
| **D2** | ¿La app se autocritica? | **No.** Producto limpio; la crítica vive en esta documentación (§12.4) |
| **D3** | Stack | **Django 6.1.1 + MySQL 8.4 + HTML/CSS/JS, JSON.** Modelos relacionales reales, sin data falsa hardcodeada (§14) |
| **D8** | Alcance | **Solo APOFYX**: landing B2B, panel de clientes, asistente y **recepción de cartera**. **Sin pagos**: ninguna tabla de pago ni de transacción (§12) |
| **D9** | Conector MySQL | **`mysqlclient`**, ya instalado y funcionando en este equipo (§14.2) |
| **D4** | Motor del asistente | **Híbrido**: reglas desde MySQL primero, **Gemini** (tier gratuito) solo como respaldo bajo el umbral de confianza (§9.3) |
| **D10** | Acceso al panel | **Panel propio** con autenticación de Django, y el admin nativo habilitado en paralelo para carga de datos (§14.5) |
| **D11** | Identidad visual | **Serpiente en teal petróleo y dorado.** Paleta muestreada del logotipo real (§14.7) |
| **D13** | Paleta de colores | **Teal `#0f4f58` como superficie, dorado `#c9a961` como acento** (§14.7) |
| **D12** | Idioma del código | **Inglés** para modelos, campos, rutas y nombres de código; **español** para documentación, interfaz y datos. En los campos con opciones el límite está en §14.3 (§14.3) |
| **D7** | Empresas y personas | **Se mantienen** los nombres de §6: Vitalis Gym, Instituto Andes, Clínica Sonrisa Norte, NetSur ISP y Torres del Parque, con sus contactos |
| **D14** | Base de datos | **Docker**, con MySQL 8.4 en contenedor y la base poblada al arrancar (§14.6) |

### 17.2 Abiertas

| # | Decisión | Estado |
| --- | --- | --- |
| **D15** | Logotipo definitivo | Los archivos actuales se extrajeron de un JPG de presentación y tienen halos en los brillos. Falta el **SVG del isotipo**, que es lo que resuelve el tamaño chico (§14.7) |

---

*Documento vivo. Toda cifra es sintética y construida para el caso.*
