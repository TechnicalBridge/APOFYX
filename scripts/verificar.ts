/*
 * Arnés de verificación visual.
 *
 * QUÉ RESUELVE
 * Casi todo el código de este repo lo escribió una máquina traduciendo la captura
 * del sitio original, y el CSS es heredado entero. Ahí un cambio inocente no se
 * nota: quitarle un `id` al footer —que parecía decoración de Webflow— le sacó
 * 302 px de alto a las 34 páginas, y eso sólo apareció al medirlo. Este arnés
 * convierte «no toqué nada visual» en un test que falla.
 *
 * QUÉ MIDE, por cada ruta y ancho
 *   · alto del documento y cantidad de nodos    → estructura
 *   · hash del texto visible                    → contenido
 *   · dos huellas visuales (arriba y abajo)     → color y disposición
 *
 * La huella es la propia captura reducida a una grilla de 16×16 en gris: cabe en
 * el JSON de la línea base, se puede versionar y diffear, y se compara con
 * tolerancia para que el antialiasing no produzca falsos positivos.
 *
 *   npm run verificar               compara contra verificacion/base.json
 *   npm run verificar -- --actualizar   reescribe la línea base
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import puppeteer from 'puppeteer-core';
import type { Page } from 'puppeteer-core';

import { RUTAS } from './rutas.ts';
import { RAIZ, DIST, buscarChrome, servirDist } from './navegador.ts';

const PUERTO = 4179;
const CARPETA = path.join(RAIZ, 'verificacion');
const BASE = path.join(CARPETA, 'base.json');
const FALLAS = path.join(CARPETA, 'actual');

const ANCHOS: [string, number, number][] = [
  ['movil', 390, 844],
  ['tablet', 820, 1180],
  ['escritorio', 1440, 900],
];

const LADO = 16; // la huella es una grilla de 16×16
const TOLERANCIA_CELDA = 1; // un escalón de gris de diferencia no cuenta
const TOLERANCIA_CELDAS = 0.02; // hasta un 2% de celdas distintas se acepta
const ESPERA_MS = 900;

const actualizar = process.argv.includes('--actualizar');

/*
 * Congela todo lo que se mueve y muestra lo que la entrada dejaría escondido.
 *
 * Sin lo primero, dos corridas iguales dan huellas distintas según en qué cuadro
 * de la animación se tomó la medida. Sin lo segundo sería peor: `.db-reveal` deja
 * el contenido en opacidad cero hasta que el observador lo destraba, así que el
 * arnés mediría una página medio vacía y no notaría nunca que una sección se
 * rompió por debajo del pliegue.
 */
const CSS_QUIETO = `
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
  }
  .db-stagger, .db-reveal {
    opacity: 1 !important;
    transform: none !important;
  }
`;

interface Medida {
  alto: number;
  nodos: number;
  altoPie: number;
  desborde: number;
  titulo: string;
  texto: string;
  arriba: string;
  abajo: string;
}

/** Los campos que, si cambian, significan que algo se movió. */
const CAMPOS: (keyof Medida)[] = ['alto', 'nodos', 'altoPie', 'titulo', 'texto'];

function comparar(a?: string, b?: string): number {
  if (!a || !b || a.length !== b.length) return 1;
  let distintas = 0;
  for (let i = 0; i < a.length; i += 1) {
    const d = Math.abs(parseInt(a[i]!, 16) - parseInt(b[i]!, 16));
    if (d > TOLERANCIA_CELDA) distintas += 1;
  }
  return distintas / a.length;
}

async function medir(pagina: Page, laboratorio: Page, url: string): Promise<Medida> {
  await pagina.goto(url, { waitUntil: 'networkidle0', timeout: 45000 });
  await pagina.addStyleTag({ content: CSS_QUIETO });
  await pagina.evaluate(() => document.fonts?.ready);
  await new Promise((r) => setTimeout(r, ESPERA_MS));

  const datos = await pagina.evaluate(() => {
    const main = document.querySelector('main') || document.body;
    const pie = document.querySelector('footer');
    return {
      alto: document.body.scrollHeight,
      nodos: main.querySelectorAll('*').length,
      texto: (document.body.innerText || '').replace(/\s+/g, ' ').trim(),
      titulo: document.title,
      altoPie: pie ? Math.round(pie.getBoundingClientRect().height) : 0,
      desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });

  const huella = async () => {
    const b64 = await pagina.screenshot({ encoding: 'base64' });
    return laboratorio.evaluate(
      async (png: string, lado: number) => {
        const img = new Image();
        img.src = `data:image/png;base64,${png}`;
        await img.decode();
        const lienzo = document.createElement('canvas');
        lienzo.width = lado;
        lienzo.height = lado;
        const ctx = lienzo.getContext('2d', { willReadFrequently: true });
        if (!ctx) return '';
        ctx.drawImage(img, 0, 0, lado, lado);
        const px = ctx.getImageData(0, 0, lado, lado).data;
        let salida = '';
        for (let i = 0; i < px.length; i += 4) {
          const gris = (px[i]! * 0.299 + px[i + 1]! * 0.587 + px[i + 2]! * 0.114) / 16;
          salida += Math.min(15, Math.floor(gris)).toString(16);
        }
        return salida;
      },
      b64,
      LADO,
    );
  };

  const arriba = await huella();
  await pagina.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await new Promise((r) => setTimeout(r, 450));
  const abajo = await huella();

  return {
    alto: datos.alto,
    nodos: datos.nodos,
    altoPie: datos.altoPie,
    desborde: datos.desborde,
    titulo: datos.titulo,
    texto: crypto.createHash('sha256').update(datos.texto).digest('hex').slice(0, 16),
    arriba,
    abajo,
  };
}

// --- arranque ---------------------------------------------------------------

if (!fs.existsSync(path.join(DIST, 'index.html'))) {
  console.error('No hay dist/. Corré `npm run build` antes de verificar.');
  process.exit(1);
}

const chrome = buscarChrome();
if (!chrome) {
  console.error('No encontré Chrome. Definí CHROME_PATH para poder verificar.');
  process.exit(1);
}

fs.mkdirSync(CARPETA, { recursive: true });
const servidor = await servirDist(PUERTO);
const navegador = await puppeteer.launch({
  executablePath: chrome,
  headless: true,
  args: ['--hide-scrollbars', '--disable-gpu', '--force-device-scale-factor=1', '--no-sandbox'],
});

const laboratorio = await navegador.newPage();
await laboratorio.goto('about:blank');

const base = !actualizar && fs.existsSync(BASE) ? JSON.parse(fs.readFileSync(BASE, 'utf8')) : null;

if (!actualizar && !base) {
  console.error('No hay línea base. Creala con `npm run verificar -- --actualizar`.');
  await navegador.close();
  servidor.close();
  process.exit(1);
}

const medido: Record<string, Medida> = {};
const problemas: { clave: string; que: string; detalle: string }[] = [];
let comprobaciones = 0;

for (const [nombreAncho, ancho, alto] of ANCHOS) {
  const pagina = await navegador.newPage();
  await pagina.setViewport({ width: ancho, height: alto, isMobile: nombreAncho === 'movil' });
  await pagina.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }]);

  for (const ruta of RUTAS) {
    const clave = `${nombreAncho} ${ruta}`;
    comprobaciones += 1;
    let ahora: Medida;
    try {
      ahora = await medir(pagina, laboratorio, `http://localhost:${PUERTO}${ruta}`);
    } catch (e) {
      problemas.push({ clave, que: 'no cargó', detalle: (e as Error).message });
      continue;
    }
    medido[clave] = ahora;

    if (!base) continue;
    const antes = base[clave];
    if (!antes) {
      problemas.push({ clave, que: 'ruta nueva', detalle: 'no está en la línea base' });
      continue;
    }

    for (const campo of CAMPOS) {
      if (antes[campo] !== ahora[campo]) {
        problemas.push({ clave, que: campo, detalle: `${antes[campo]} → ${ahora[campo]}` });
      }
    }
    if (ahora.desborde > 1) {
      problemas.push({ clave, que: 'desborde horizontal', detalle: `${ahora.desborde}px` });
    }
    for (const zona of ['arriba', 'abajo'] as const) {
      const deriva = comparar(antes[zona], ahora[zona]);
      if (deriva > TOLERANCIA_CELDAS) {
        problemas.push({
          clave,
          que: `huella ${zona}`,
          detalle: `${(deriva * 100).toFixed(1)}% de celdas movidas`,
        });
      }
    }
  }
  await pagina.close();
}

await navegador.close();
servidor.close();

if (actualizar) {
  fs.writeFileSync(BASE, `${JSON.stringify(medido, null, 1)}\n`);
  console.log(`Línea base escrita: ${comprobaciones} comprobaciones en verificacion/base.json`);
  process.exit(0);
}

if (!problemas.length) {
  console.log(`Verificación correcta: ${comprobaciones}/${comprobaciones} sin cambios.`);
  process.exit(0);
}

// Al fallar deja las capturas de las rutas afectadas, para poder mirarlas.
fs.mkdirSync(FALLAS, { recursive: true });
console.error(
  `\nVerificación fallida: ${problemas.length} diferencia(s) sobre ${comprobaciones} comprobaciones.\n`,
);
for (const p of problemas) {
  console.error(`  ${p.clave.padEnd(48)} ${p.que}: ${p.detalle}`);
}
console.error('\nSi el cambio es intencional, revisalo y actualizá la base con:');
console.error('  npm run verificar -- --actualizar\n');
process.exit(1);
