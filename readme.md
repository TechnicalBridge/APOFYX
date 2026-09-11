# DataBridge

Sitio público de **DataBridge**, una inmobiliaria ficticia creada para un trabajo de
capstone. La empresa, los proyectos, las comunas donde dice tener paños, los precios
y las personas citadas son inventados: nada de lo que se lee es una oferta.

## Qué es DataBridge dentro del proyecto

El proyecto general tiene dos frentes y conviene no confundirlos:

|               | **DataBridge** (esta repo) | **Technical Bridge** (otra repo) |
| ------------- | -------------------------- | -------------------------------- |
| Qué es        | Una inmobiliaria           | El portal del deudor             |
| Rol           | **Acreedor**               | Intermediario de pagos           |
| Este sitio    | Su web pública             | —                                |
| Quién lo mira | Alguien que quiere comprar | Alguien que ya debe              |

DataBridge es **el cliente**, no la plataforma. Vende parcelas, sitios y casas con
**financiamiento directo** —cuotas fijas en UF, sin banco—, y por eso se queda con
una cartera propia de compradores pagando mes a mes durante cinco años. Eso es lo que
la convierte en acreedora y lo que la hace servir de cliente de prueba realista.

Esta repo contiene **sólo la web de la inmobiliaria**. No implementa portal de
deudor, ni pagos, ni repactación: eso es Technical Bridge y vive aparte.

## La tesis del sitio

Es el sitio de un acreedor que financia a cinco años, y todo el copy sale de ahí:

1. **El paño se elige con datos.** La empresa partió tasando suelo en 2014 —de ahí el
   nombre— y todavía publica lo que otro folleto escondería: los dos kilómetros de
   ripio, el loteo que todavía no tiene recepción municipal.
2. **El precio se ve sin dejar datos.** El cotizador está en el sitio público y no
   pide teléfono. Obligar a entregar el contacto para conocer una cuota es lo normal
   del rubro y es justo la fricción que esta empresa dice no tener.
3. **La política de mora está escrita antes de firmar.** `/financiamiento` publica
   los días de gracia, cuándo corre interés y cuándo se ofrece repactar. Quien compra
   a sesenta cuotas va a tener un mes malo; saberlo antes cambia la decisión.

## Cómo se corre

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # compila y escribe un HTML por ruta en dist/
npm run preview    # sirve dist/ como lo haría un hosting estático

npm run tipos      # tsc --noEmit
npm run lint
npm run formato
npm test
npm run verificar  # compara el render contra la línea base
```

`npm run build` termina con un paso de prerenderizado que necesita Chrome. Si no lo
encuentra, avisa y deja `dist/` como SPA en vez de romper el build; se le puede
indicar la ruta con `CHROME_PATH`.

**No uses `vite preview` para revisar el build**: reescribe toda petición a
`index.html` y las páginas prerenderizadas nunca se ven. Para eso está
`npm run preview`.

## Qué hay adentro

```
scripts/
  verificar.ts       el arnés: compara el render contra verificacion/base.json
  prerender.ts       escribe un HTML real por ruta
  servir.ts          sirve dist/ como un hosting estático
  rutas.ts           las rutas — las fichas salen del dominio, no de una lista
src/
  app/               App, main, nav y pie
  pages/             una por ruta
  sections/          los bloques de la portada, reutilizables entre páginas
  ui/                marca, foto, plano de loteo, tarjeta de proyecto, cotizador
  domain/            company.ts · projects.ts · financing.ts · photo-credits.ts
  services/          el borde de datos: content, contact, http
  hooks/             entradas por scroll, contadores, metadatos por ruta
  styles/            base (tokens) · components · sections · pages
tests/               el contenido ficticio, la aritmética del financiamiento y las rutas
```

Todo es TypeScript en modo estricto. Ninguna sección importa de `domain/`
directamente: pide a `services/content.ts`, para que el día que los proyectos y la
disponibilidad vengan de una API no haya que tocar ninguna pantalla.

### Las imágenes

Las fotos viven en `public/fotos/      las imágenes del sitio
public/fotos/` y se llaman por el slug del proyecto:
`altos-de-panguilemu-1.jpg`, `-2.jpg`, etc. La primera de cada proyecto es la
portada —abre la ficha a sangre y va en la tarjeta del listado— y el resto arma la
galería. **Cambiar una imagen es reemplazar el archivo**; el pie se ajusta en el
campo `fotos` de `domain/projects.ts`.

Son de terceros y están bajo licencias Creative Commons, que permiten reutilizarlas
y modificarlas —acá se reescalaron a 1600 px y se recomprimieron— a cambio de
nombrar al autor. Esa atribución está en `domain/photo-credits.ts` y se muestra en
`/creditos`. Hay un test que falla si se agrega una foto sin su crédito.

El **plano de loteo** sí se dibuja (`ui/SitePlan.tsx`), a partir de las unidades y
la disponibilidad de cada proyecto: los lotes pintados son los vendidos y los
vacíos los que quedan. Cierra la galería porque responde lo que una foto no puede
—cuál lote es cuál y cuántos quedan— y se actualiza solo cuando cambia la ficha.

`ui/Photo.tsx` envuelve a `<img>` para que la caja reserve su lugar antes de que la
imagen cargue, para diferir todo lo que no esté en el primer pantallazo, y para que
el hueco mientras carga sea de color tierra y no gris.

### El diseño

La paleta es la del lugar: papel frío con sesgo verde, verde pino para los bloques
oscuros y **un solo acento**, un ocre de pasto seco, que se gasta en los enlaces, el
lote vendido del plano y la cifra que importa. Titulares en Newsreader, texto y datos
en Archivo con cifras tabulares para que los precios se comparen en columna.

Los colores semánticos (correcto, aviso, alerta) están separados del acento a
propósito.

### La animación

Dos primitivas y nada más:

| clase         | cuándo entra                                  |
| ------------- | --------------------------------------------- |
| `.db-stagger` | al montar — para lo que está sobre el pliegue |
| `.db-reveal`  | al llegar al scroll, con `useInView`          |

El escalonado se pasa por la variable `--retraso` desde el componente, así no hace
falta una clase por índice. Nada dura más de medio segundo y ninguna curva rebota.

Con `prefers-reduced-motion` el contenido aparece completo y quieto desde el primer
cuadro. No es una versión degradada: es el mismo contenido sin la parte que molesta.

## Rutas

`/` · `/proyectos` · `/proyectos/:slug` (seis) · `/financiamiento` · `/nosotros` ·
`/contacto` · `/creditos` · `/terminos` · `/privacidad`

Catorce documentos en total. Cada uno sale del build con su propio `<title>`,
descripción y tarjeta de enlace: una ficha de proyecto es exactamente lo que la gente
copia y manda por WhatsApp.

## Cómo se comprueba que no se rompió

`npm run verificar` mide cada ruta en tres anchos (390 · 820 · 1440 px) y compara
contra `verificacion/base.json`: alto del documento, cantidad de nodos, desborde
horizontal, hash del texto y dos huellas visuales de 16×16 por página.

Existe porque en un sitio con mucho CSS los bugs no son de sintaxis, son de píxeles:
se compila, no tira ningún error y la página quedó 300 px más corta.

La CI corre tipos, linter, formato, tests y build en cada push.
