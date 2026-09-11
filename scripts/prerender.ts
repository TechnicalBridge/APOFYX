/*
 * Escribe un HTML real por cada ruta, dentro de dist/.
 *
 * POR QUÉ HACE FALTA
 * Una SPA manda la misma cáscara vacía para todas las URL y arma el contenido con
 * JavaScript, así que un rastreador, la vista previa de un enlace en WhatsApp o un
 * «ver código fuente» encuentran una página en blanco. Para una inmobiliaria eso es
 * caro de verdad: las fichas de proyecto son justo lo que la gente busca y comparte,
 * y compartir un enlace que se previsualiza vacío es perder la consulta.
 *
 * El HTML resultante sigue arrancando React encima: esto no reemplaza la app, le
 * pone debajo un documento que se sostiene solo.
 */
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

import { RUTAS } from './rutas.ts';
import { DIST, buscarChrome, servirDist } from './navegador.ts';

const PUERTO = 4178;

/*
 * Las clases de entrada se quitan del HTML que se escribe a disco.
 *
 * Las dos dejan el elemento en opacidad cero hasta que algo las destraba, y
 * `.db-reveal` además depende de un observador que sólo corre con JavaScript. Si se
 * quedaran, el documento estático serviría todas las secciones bajo el pliegue
 * invisibles: exactamente lo que este script existe para evitar.
 *
 * React vuelve a ponerlas al montar, así que la animación no se pierde para quien
 * sí ejecuta JavaScript.
 */
const CLASES_DE_ANIMACION = ['db-stagger', 'db-reveal'];

const chrome = buscarChrome();
if (!chrome) {
  // Que la falta de un navegador no rompa el build: queda la SPA, que se ve igual
  // en el navegador. Lo que se pierde es el HTML para quien no ejecuta JavaScript.
  console.warn(
    '\n[prerender] No encontré Chrome. Definí CHROME_PATH para generar el HTML por ruta.',
  );
  console.warn('[prerender] dist/ queda como SPA.\n');
  process.exit(0);
}

const servidor = await servirDist(PUERTO);
const navegador = await puppeteer.launch({
  executablePath: chrome,
  headless: true,
  args: ['--disable-gpu', '--no-sandbox'],
  defaultViewport: { width: 1440, height: 900 },
});

let escritas = 0;
for (const ruta of RUTAS) {
  const pagina = await navegador.newPage();
  try {
    await pagina.goto(`http://localhost:${PUERTO}${ruta}`, {
      waitUntil: 'networkidle0',
      timeout: 45000,
    });
    await new Promise((r) => setTimeout(r, 350));

    const html = await pagina.evaluate((clases) => {
      clases.forEach((c) => {
        document.querySelectorAll(`.${c}`).forEach((n) => n.classList.remove(c));
      });
      return `<!DOCTYPE html>\n${document.documentElement.outerHTML}`;
    }, CLASES_DE_ANIMACION);

    const destino =
      ruta === '/' ? path.join(DIST, 'index.html') : path.join(DIST, ruta.slice(1), 'index.html');
    fs.mkdirSync(path.dirname(destino), { recursive: true });
    fs.writeFileSync(destino, html);
    escritas += 1;
    console.log(`[prerender] ${ruta.padEnd(52)} ${(html.length / 1024).toFixed(0)} kB`);
  } catch (e) {
    console.warn(`[prerender] ${ruta} falló: ${(e as Error).message}`);
  }
  await pagina.close();
}

await navegador.close();
servidor.close();
console.log(`\n[prerender] ${escritas}/${RUTAS.length} páginas escritas.`);
