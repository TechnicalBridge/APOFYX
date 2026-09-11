/*
 * Sirve dist/ como lo haría un hosting estático: primero el archivo real de cada
 * ruta (dist/industrias/salud/index.html) y sólo si no existe, la portada.
 *
 * `vite preview` no sirve para revisar esto: reescribe TODA petición a index.html,
 * así que las páginas prerenderizadas nunca se ven y el resultado parece una SPA
 * aunque no lo sea.
 */
import { servirDist } from './navegador.ts';

const puerto = Number(process.env.PORT || 4173);
await servirDist(puerto);
console.log(`dist/ servido en http://localhost:${puerto}`);
