import type { Proyecto } from '../domain/projects';

/*
 * La geometría del loteo, compartida por las dos vistas que dibuja el sitio.
 *
 * `TerrainView` pinta el paño desde arriba y `SitePlan` el plano técnico. Los dos
 * tienen que mostrar exactamente la misma subdivisión: si cada uno calculara sus
 * lotes por su cuenta, la imagen y el plano del mismo proyecto terminarían
 * contradiciéndose, que es peor que no tener imagen.
 *
 * DETERMINISTA A PROPÓSITO
 * La variación entre proyectos sale de un generador sembrado con el slug, nunca de
 * Math.random. Dos motivos: un proyecto se dibuja siempre igual —el comprador que
 * vuelve ve el mismo paño—, y el HTML que escribe el prerender coincide con el que
 * React genera en el navegador. Con azar real, cada carga movería los deslindes.
 */

/** Generador sembrado (FNV-1a + mulberry32). Mismo texto, misma secuencia. */
export function sembrar(texto: string) {
  let h = 2166136261;
  for (let i = 0; i < texto.length; i += 1) {
    h ^= texto.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h += 0x6d2b79f5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Semilla numérica estable, para los filtros SVG que piden un entero. */
export const semillaDe = (texto: string) => Math.floor(sembrar(texto)() * 1000);

export interface Caja {
  ancho: number;
  alto: number;
  margen: number;
}

export interface Lote {
  x: number;
  y: number;
  w: number;
  h: number;
  vendido: boolean;
}

export interface Calle {
  y: number;
  alto: number;
}

export interface Loteo {
  lotes: Lote[];
  /** Los caminos interiores, para que la vista aérea pueda pintarlos. */
  calles: Calle[];
}

/**
 * Reparte las unidades en manzanas enfrentadas a un camino interior, que es como
 * se lotea de verdad: dos bandas de sitios por calle, no una grilla suelta.
 */
export function trazarLoteo(proyecto: Proyecto, caja: Caja): Loteo {
  const azar = sembrar(proyecto.slug);
  const { unidades, disponibles } = proyecto;
  const vendidas = unidades - disponibles;

  // Sobre unas cincuenta unidades una sola calle deja los sitios demasiado
  // angostos para leerse, así que el loteo se parte en dos manzanas.
  const manzanas = unidades > 50 ? 2 : 1;
  const porBanda = Math.ceil(unidades / (manzanas * 2));

  const util = { w: caja.ancho - caja.margen * 2, h: caja.alto - caja.margen * 2 };
  const calleAlto = caja.alto * 0.072;
  const entreManzanas = caja.alto * 0.048;
  const altoManzana = (util.h - entreManzanas * (manzanas - 1)) / manzanas;
  const altoBanda = (altoManzana - calleAlto) / 2;

  const lotes: Lote[] = [];
  const calles: Calle[] = [];
  let n = 0;

  for (let m = 0; m < manzanas; m += 1) {
    const topeManzana = caja.margen + m * (altoManzana + entreManzanas);
    calles.push({ y: topeManzana + altoBanda, alto: calleAlto });

    for (let banda = 0; banda < 2; banda += 1) {
      const y = banda === 0 ? topeManzana : topeManzana + altoBanda + calleAlto;

      // Los deslindes se corren un poco para que no parezca papel cuadriculado.
      // El corrimiento es del borde, no del ancho, así la banda cierra exacta.
      const cortes: number[] = [];
      for (let i = 0; i <= porBanda; i += 1) {
        const base = caja.margen + (util.w * i) / porBanda;
        const holgura = i === 0 || i === porBanda ? 0 : (azar() - 0.5) * (util.w / porBanda) * 0.34;
        cortes.push(base + holgura);
      }

      for (let i = 0; i < porBanda && n < unidades; i += 1) {
        const x = cortes[i]!;
        const siguiente = cortes[i + 1]!;
        lotes.push({
          x: x + 0.75,
          y: y + 0.75,
          w: siguiente - x - 1.5,
          h: altoBanda - 1.5,
          vendido: n < vendidas,
        });
        n += 1;
      }
    }
  }

  return { lotes, calles };
}

/** El edificio se dibuja de frente: pisos y unidades por piso. */
export function trazarEdificio(proyecto: Proyecto, caja: Caja): Lote[] {
  const { unidades, disponibles } = proyecto;
  const vendidas = unidades - disponibles;
  const porPiso = Math.min(10, Math.max(4, Math.round(Math.sqrt(unidades))));
  const pisos = Math.ceil(unidades / porPiso);

  const suelo = caja.alto * 0.056;
  const util = { w: caja.ancho - caja.margen * 2, h: caja.alto - caja.margen * 2 - suelo };
  const anchoUnidad = util.w / porPiso;
  const altoUnidad = util.h / pisos;

  const celdas: Lote[] = [];
  let n = 0;

  for (let piso = 0; piso < pisos; piso += 1) {
    for (let i = 0; i < porPiso && n < unidades; i += 1) {
      celdas.push({
        x: caja.margen + i * anchoUnidad + anchoUnidad * 0.07,
        // Los pisos bajos se venden primero, así que el relleno sube desde abajo.
        y: caja.margen + (pisos - 1 - piso) * altoUnidad + altoUnidad * 0.09,
        w: anchoUnidad * 0.86,
        h: altoUnidad * 0.82,
        vendido: n < vendidas,
      });
      n += 1;
    }
  }

  return celdas;
}
