/*
 * Las rutas del sitio, en un solo lugar.
 *
 * Las usan el prerender (para escribir un HTML por ruta) y el arnés de
 * verificación. Si vivieran duplicadas, agregar una página dejaría a una de las dos
 * mirando para otro lado.
 *
 * Las fichas de proyecto salen del dominio en vez de estar escritas acá: son la
 * parte que cambia —se agrega un loteo, se cierra otro— y una lista a mano se
 * desincroniza el día que alguien publique un proyecto y olvide prerenderizarlo.
 */
import { PROYECTOS } from '../src/domain/projects.ts';

export const RUTAS = [
  '/',
  '/proyectos',
  ...PROYECTOS.map((p) => `/proyectos/${p.slug}`),
  '/financiamiento',
  '/nosotros',
  '/contacto',
  '/creditos',
  '/terminos',
  '/privacidad',
];

export default RUTAS;
