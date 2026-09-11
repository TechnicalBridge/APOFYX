/*
 * Los proyectos de DataBridge.
 *
 * Seis desarrollos ficticios en el Maule y Ñuble. Cada uno trae lo que un
 * comprador pregunta primero y lo que los folletos suelen omitir: cuántas
 * unidades quedan, cómo se llega en invierno, qué está urbanizado y qué no.
 *
 * SOBRE LAS IMÁGENES
 * Cada proyecto trae sus fotos en `fotos`, y la primera es la portada: es la que
 * abre la ficha a sangre y la que va en la tarjeta del listado. Los archivos viven
 * en `public/fotos/` y se llaman como el slug, así que cambiar una imagen es
 * reemplazar un archivo y, si hace falta, ajustar su pie acá.
 *
 * Las fotos son de terceros bajo licencia Creative Commons e ilustran proyectos
 * inventados. La atribución que esas licencias exigen está en `photo-credits.ts` y
 * se muestra en /creditos.
 *
 * El plano de loteo sí se dibuja, en `ui/SitePlan.tsx`, a partir de las unidades y
 * la disponibilidad de cada proyecto. Cierra la galería porque responde lo que una
 * foto no puede: cuál lote es cuál y cuáles quedan.
 */

export type TipoProyecto = 'parcelas' | 'sitios' | 'casas' | 'departamentos';
export type EstadoProyecto = 'en-venta' | 'en-construccion' | 'entregado' | 'proximamente';

/**
 * Cómo se ve el paño desde arriba.
 *
 * Cinco descriptores bastan para que la vista aérea de cada proyecto se distinga
 * de las demás sin inventar nada: salen de lo que ya dice la descripción.
 */
export interface Paisaje {
  relieve: 'plano' | 'ondulado' | 'urbano';
  /** La paleta del suelo. El secano maulino no es verde en marzo. */
  tono: 'secano' | 'riego' | 'urbano' | 'bosque';
  agua: 'canal' | 'estero' | 'ninguno';
  /** Densidad de arbolado, de 0 a 1. */
  arboles: number;
  /** Por dónde entra el camino de acceso. */
  acceso: 'norte' | 'sur' | 'oriente' | 'poniente';
}

/**
 * Coordenadas reales de la comuna, no del loteo — el loteo es inventado.
 *
 * Sirven para ubicar el proyecto en el mapa de la zona: las comunas sí existen y
 * las distancias entre ellas son las de verdad, que es la información que alguien
 * necesita para saber si le queda lejos.
 */
export interface Coordenadas {
  lat: number;
  lon: number;
}

/** Una foto del proyecto. La primera de la lista es la portada. */
export interface Foto {
  /** Nombre del archivo dentro de public/fotos/. */
  archivo: string;
  /** Lo que se ve. Sirve de pie y de texto alternativo. */
  pie: string;
}

export interface Proyecto {
  slug: string;
  nombre: string;
  tipo: TipoProyecto;
  estado: EstadoProyecto;
  comuna: string;
  region: string;
  /** Abre la portada. Sólo uno. */
  destacado?: boolean;
  /** Una línea para la tarjeta del listado. */
  resumen: string;
  /** Dos o tres párrafos para la ficha. */
  descripcion: string[];
  superficie: string;
  desdeUF: number;
  unidades: number;
  disponibles: number;
  entrega: string;
  /** Lo que está hecho y lo que no. Sin adjetivos. */
  atributos: string[];
  /** Meses de financiamiento directo disponibles para este proyecto. */
  plazoMaximo: number;
  fotos: Foto[];
  paisaje: Paisaje;
  coordenadas: Coordenadas;
}

export const ETIQUETA_TIPO: Record<TipoProyecto, string> = {
  parcelas: 'Parcelas',
  sitios: 'Sitios urbanizados',
  casas: 'Casas',
  departamentos: 'Departamentos',
};

export const ETIQUETA_ESTADO: Record<EstadoProyecto, string> = {
  'en-venta': 'En venta',
  'en-construccion': 'En construcción',
  entregado: 'Entregado',
  proximamente: 'Próximamente',
};

export const PROYECTOS: Proyecto[] = [
  {
    slug: 'altos-de-panguilemu',
    nombre: 'Altos de Panguilemu',
    tipo: 'parcelas',
    estado: 'en-venta',
    comuna: 'San Clemente',
    region: 'Región del Maule',
    destacado: true,
    resumen: 'Parcelas de 5.000 m² a 22 km de Talca, urbanizadas y con entrega inmediata.',
    descripcion: [
      'Cuarenta y ocho parcelas de media hectárea en la subida a Panguilemu, sobre terreno con pendiente suave hacia el poniente. El paño lo compramos en 2023 después de descartar otros dos en el mismo sector: uno no tenía derechos de agua inscritos y el otro dependía de una servidumbre de tránsito que el vecino podía cerrar.',
      'La urbanización está terminada. Eso significa camino interior de ripio compactado con cuneta, electricidad tendida hasta el deslinde de cada parcela y pozo profundo con derecho de aprovechamiento inscrito a nombre de la comunidad. Se entrega de inmediato: no hay obras pendientes que esperar.',
      'El acceso es por ruta pavimentada hasta el kilómetro 20 y ripio los últimos dos. Lo decimos porque en invierno esos dos kilómetros importan, y porque conviene verlos antes de firmar y no después.',
    ],
    superficie: '5.000 m²',
    desdeUF: 1180,
    unidades: 48,
    disponibles: 17,
    entrega: 'Inmediata',
    atributos: [
      'Camino interior de ripio compactado con cuneta',
      'Electricidad trifásica hasta el deslinde',
      'Pozo profundo con derecho de agua inscrito',
      'Rol propio y deslindes inscritos por parcela',
      'A 22 km de Talca: 20 pavimentados, 2 de ripio',
    ],
    fotos: [
      { archivo: 'altos-de-panguilemu-1.jpg', pie: 'El paño desde el camino de acceso' },
      {
        archivo: 'altos-de-panguilemu-2.jpg',
        pie: 'La pendiente hacia el poniente, al final de la tarde',
      },
    ],
    paisaje: {
      relieve: 'ondulado',
      tono: 'secano',
      agua: 'ninguno',
      arboles: 0.42,
      acceso: 'poniente',
    },
    coordenadas: { lat: -35.537, lon: -71.486 },
    plazoMaximo: 60,
  },
  {
    slug: 'vega-alegre-iii',
    nombre: 'Vega Alegre III',
    tipo: 'parcelas',
    estado: 'en-venta',
    comuna: 'Linares',
    region: 'Región del Maule',
    resumen: 'Tercera etapa del loteo con que partimos en 2017. Suelo plano y canal de regadío.',
    descripcion: [
      'Treinta y seis parcelas planas de 5.000 m² en la última etapa de Vega Alegre, el primer paño que compramos y loteamos nosotros. Las dos etapas anteriores están vendidas y escrituradas, así que el sector ya está habitado: hay vecinos, luz encendida y el camino tiene uso.',
      'El suelo es agrícola de buena calidad y el canal de regadío corre por el deslinde norte del loteo. Las parcelas que dan al canal tienen acciones de agua incluidas en el precio; el resto se abastece del pozo comunitario. Cuál es cuál está en el plano y en la promesa.',
    ],
    superficie: '5.000 m²',
    desdeUF: 940,
    unidades: 36,
    disponibles: 31,
    entrega: 'Inmediata',
    atributos: [
      'Suelo plano, uso agrícola',
      'Canal de regadío por el deslinde norte',
      'Acciones de agua incluidas en las parcelas ribereñas',
      'Dos etapas anteriores ya entregadas y escrituradas',
      'A 9 km de Linares por camino público',
    ],
    fotos: [
      { archivo: 'vega-alegre-iii-1.jpg', pie: 'El sector desde el aire: suelo plano y en uso' },
      { archivo: 'vega-alegre-iii-2.jpg', pie: 'Las etapas anteriores, ya habitadas' },
    ],
    paisaje: { relieve: 'plano', tono: 'riego', agua: 'canal', arboles: 0.3, acceso: 'norte' },
    coordenadas: { lat: -35.846, lon: -71.593 },
    plazoMaximo: 60,
  },
  {
    slug: 'lomas-de-cauquenes',
    nombre: 'Lomas de Cauquenes',
    tipo: 'sitios',
    estado: 'en-venta',
    comuna: 'Cauquenes',
    region: 'Región del Maule',
    resumen:
      'Sitios urbanizados dentro del límite urbano, con alcantarillado y permiso de edificación.',
    descripcion: [
      'Setenta y cuatro sitios de entre 400 y 620 m² en el borde norte de Cauquenes, dentro del límite urbano. Esa última parte es la que cambia todo: al estar adentro tienen alcantarillado, agua potable de la red y permiso de edificación tramitable, cosa que una parcela de agrado no tiene.',
      'Es el proyecto más barato que vendemos y el que más rápido se construye. La mayoría de los compradores levanta la casa por autoconstrucción en etapas, y el financiamiento a 48 meses está pensado para que la cuota del sitio conviva con eso.',
    ],
    superficie: '400 a 620 m²',
    desdeUF: 610,
    unidades: 74,
    disponibles: 58,
    entrega: 'Inmediata',
    atributos: [
      'Dentro del límite urbano de Cauquenes',
      'Alcantarillado y agua potable de la red',
      'Calles pavimentadas y luminarias instaladas',
      'Permiso de edificación tramitable',
      'Uso mixto permitido en los sitios de la avenida',
    ],
    fotos: [
      {
        archivo: 'lomas-de-cauquenes-1.jpg',
        pie: 'El borde norte de Cauquenes, donde está el loteo',
      },
      { archivo: 'lomas-de-cauquenes-2.jpg', pie: 'Una casa terminada en un sitio del proyecto' },
    ],
    paisaje: { relieve: 'urbano', tono: 'urbano', agua: 'ninguno', arboles: 0.22, acceso: 'sur' },
    coordenadas: { lat: -35.967, lon: -72.353 },
    plazoMaximo: 48,
  },
  {
    slug: 'barrio-los-robles',
    nombre: 'Barrio Los Robles',
    tipo: 'casas',
    estado: 'en-construccion',
    comuna: 'Chillán',
    region: 'Región de Ñuble',
    resumen: 'Cincuenta y dos casas de 92 m² en sitios de 300 m². Entrega en marzo de 2027.',
    descripcion: [
      'Casas de 92 m² construidos en sitios de 300 m², en un condominio cerrado al oriente de Chillán. Tres dormitorios, dos baños y un antejardín que da para estacionar dos autos sin invadir la vereda.',
      'La obra está en la etapa de terminaciones de la primera manzana y la entrega comprometida es marzo de 2027. Publicamos el avance real cada mes: si se corre la fecha, se avisa cuando se sabe y no cuando toca entregar.',
      'Es el único proyecto donde el financiamiento directo cubre sólo el pie. El saldo va con crédito hipotecario, porque el monto y la obra construida lo permiten — y a esa escala el banco sale más barato que nosotros.',
    ],
    superficie: '92 m² en sitio de 300 m²',
    desdeUF: 2980,
    unidades: 52,
    disponibles: 29,
    entrega: 'Marzo de 2027',
    atributos: [
      'Tres dormitorios y dos baños',
      'Condominio cerrado con acceso controlado',
      'Aislación térmica sobre norma para la zona 5',
      'Pie financiado directo; saldo con hipotecario',
      'A 6 km del centro de Chillán',
    ],
    fotos: [
      { archivo: 'barrio-los-robles-1.jpg', pie: 'La primera manzana, en etapa de terminaciones' },
      { archivo: 'barrio-los-robles-2.jpg', pie: 'Estructura de la segunda etapa' },
    ],
    paisaje: {
      relieve: 'urbano',
      tono: 'riego',
      agua: 'ninguno',
      arboles: 0.38,
      acceso: 'oriente',
    },
    coordenadas: { lat: -36.607, lon: -72.103 },
    plazoMaximo: 36,
  },
  {
    slug: 'mirador-del-maule',
    nombre: 'Mirador del Maule',
    tipo: 'departamentos',
    estado: 'entregado',
    comuna: 'Talca',
    region: 'Región del Maule',
    resumen:
      'Nuestro primer edificio, a cuatro cuadras de la Plaza de Armas. Quedan tres unidades.',
    descripcion: [
      'Sesenta y cuatro departamentos de 2 y 3 dormitorios entregados en 2024, a cuatro cuadras de la Plaza de Armas de Talca. Fue el primer edificio que desarrollamos después de diez años haciendo loteos, y se nota en las decisiones: plantas simples, sin espacios de adorno y con bodega para todas las unidades.',
      'El edificio está habitado y con administración funcionando desde la entrega. Quedan tres departamentos disponibles, todos de 3 dormitorios en los pisos altos. Se pueden visitar cualquier día de semana sin agendar.',
    ],
    superficie: '54 a 78 m²',
    desdeUF: 2340,
    unidades: 64,
    disponibles: 3,
    entrega: 'Entregado en 2024',
    atributos: [
      '2 y 3 dormitorios, todos con bodega',
      'Estacionamiento subterráneo',
      'Administración en funcionamiento desde 2024',
      'A cuatro cuadras de la Plaza de Armas',
      'Se puede visitar sin agendar',
    ],
    fotos: [{ archivo: 'mirador-del-maule-1.jpg', pie: 'El edificio, entregado en 2024' }],
    paisaje: { relieve: 'urbano', tono: 'urbano', agua: 'ninguno', arboles: 0.16, acceso: 'norte' },
    coordenadas: { lat: -35.426, lon: -71.655 },
    plazoMaximo: 36,
  },
  {
    slug: 'quebrada-honda',
    nombre: 'Quebrada Honda',
    tipo: 'parcelas',
    estado: 'proximamente',
    comuna: 'Pelarco',
    region: 'Región del Maule',
    resumen: 'Treinta parcelas en trámite de recepción municipal. Lista de espera abierta.',
    descripcion: [
      'Treinta parcelas de 5.000 m² en Pelarco, con el loteo aprobado y la recepción municipal en trámite. No vendemos nada hasta que esa recepción esté firmada: se puede anotar en la lista de espera, pero no se reciben reservas ni pagos.',
      'Lo decimos así de derecho porque en este rubro es común vender sobre un loteo que todavía no existe legalmente, y el comprador se entera cuando quiere escriturar. Estimamos apertura de ventas para el primer trimestre de 2027.',
    ],
    superficie: '5.000 m²',
    desdeUF: 1050,
    unidades: 30,
    disponibles: 30,
    entrega: 'Apertura estimada: primer trimestre de 2027',
    atributos: [
      'Loteo aprobado, recepción municipal en trámite',
      'Sin reservas ni pagos hasta la recepción',
      'Estudio de derechos de agua terminado',
      'A 18 km de Talca',
    ],
    fotos: [
      { archivo: 'quebrada-honda-1.jpg', pie: 'El camino de acceso al paño' },
      { archivo: 'quebrada-honda-2.jpg', pie: 'El terreno antes de urbanizar' },
    ],
    paisaje: { relieve: 'ondulado', tono: 'bosque', agua: 'estero', arboles: 0.62, acceso: 'sur' },
    coordenadas: { lat: -35.363, lon: -71.458 },
    plazoMaximo: 60,
  },
];

export default PROYECTOS;
