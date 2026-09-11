# Cómo trabajar en este repo

## Antes de abrir un PR

```bash
npm run tipos
npm run lint
npm run formato
npm test
npm run build
npm run verificar
```

La CI corre lo mismo. El último es el que importa de verdad: los otros cinco se
pueden aprobar con el sitio visualmente roto.

## El arnés

`npm run verificar` mide cada ruta en tres anchos y la compara contra
`verificacion/base.json`. Si algo se movió, falla y dice qué.

Si el cambio era intencional, mirá el detalle, confirmá que la diferencia es la que
buscabas y recién ahí:

```bash
npm run verificar -- --actualizar
```

Actualizar la base sin mirar convierte el arnés en un sello de goma.

## DataBridge es el acreedor, no la plataforma

Esta repo es la **web pública de una inmobiliaria ficticia**. Technical Bridge —el
portal del deudor, con pagos y repactación— es otro proyecto y vive en otra repo.

La confusión es fácil porque los dos hablan de cuotas, así que la línea es ésta: acá
se vende suelo, no software. Hay un test que falla si el contenido empieza a sonar a
producto tecnológico.

## El contenido es ficticio, y tiene que seguir siéndolo

La empresa, los seis proyectos, las comunas, los precios y las personas citadas están
inventados. Viven en `src/domain/` —`company.ts`, `projects.ts`, `financing.ts`— y de
ahí sale todo el copy del sitio.

Tres reglas:

- **No metas datos de empresas o personas reales**, ni siquiera de ejemplo. Menos
  todavía datos de deudores: este sitio no es lugar para una cartera de verdad.
- **No menciones el proyecto anterior.** Hay un test que falla si aparece la palabra,
  y está ahí a propósito.
- **Los números tienen que cerrar.** `disponibles` nunca puede superar `unidades`, y
  el pie más las cuotas tienen que dar el precio. Los tests lo comprueban: es lo
  único del sitio que calcula plata.

## Fotos

Van en `public/fotos/`, nombradas `<slug-del-proyecto>-<n>.jpg`. Para cambiar una,
reemplazá el archivo y listo; el pie está en el campo `fotos` de
`domain/projects.ts`.

Tres reglas:

- **Toda foto necesita su crédito** en `domain/photo-credits.ts`, con autor,
  licencia y enlace al original. Las licencias Creative Commons obligan a atribuir,
  y un test falla si falta el crédito de una imagen en uso.
- **Sólo licencias que permitan modificar** (CC0, PDM, CC BY, CC BY-SA). Las fotos
  se recortan y se reescalan, así que las ND quedan fuera.
- **Reescalá antes de subirlas**: 1600 px de ancho y calidad ~0.78. Una foto de
  4000 px en una tarjeta de 380 px es medio megabyte tirado.

El plano de loteo no es una foto: lo dibuja `ui/SitePlan.tsx` desde los datos del
proyecto y no hay que tocarlo al cambiar imágenes.

## Animación

Sólo dos primitivas, y conviene no agregar una tercera sin motivo:

- `.db-stagger` entra al montar — para lo que está sobre el pliegue.
- `.db-reveal` entra al llegar al scroll, destrabada por el `.db-revealed` que pone
  `ui/Section.tsx` con el hook `useInView`.

El retraso se pasa por `--retraso` desde el componente. Nada dura más de medio
segundo y ninguna curva rebota.

Las dos clases se quitan del HTML que escribe el prerender: dejan el elemento en
opacidad cero, así que sin sacarlas el documento estático serviría medio sitio
invisible.

Antes de dar una animación por terminada, miralá con `prefers-reduced-motion`
activo. El contenido tiene que verse **completo y quieto**, nunca a medias ni en
blanco.

## Estilos

- Todo va con prefijo `db-`.
- Los colores salen de los tokens de `base.css`. Ningún literal suelto en un
  componente: si un color no está en los tokens, primero se agrega ahí.
- El acento es uno solo y señala estado. Los semánticos (correcto, aviso, alerta)
  son otra cosa y no se mezclan con él.
- Lo ancho —tablas, diagramas— scrollea en su propio contenedor. La página nunca se
  mueve de lado.

## Rutas

Se declaran en `scripts/rutas.ts`, que es de donde las leen el prerender y el arnés.
Agregar una ruta al router sin agregarla ahí deja la página fuera del build estático
y fuera de la verificación.

Las fichas de proyecto son la excepción: salen solas de `PROYECTOS`, así que publicar
un loteo nuevo ya lo deja prerenderizado. Toda página nueva además tiene que llamar a
`useMeta`, o sale al mundo con el título de la anterior.
