/*
 * Piezas compartidas por el prerender y el arnés: encontrar Chrome y servir dist/.
 */
import fs from 'node:fs';
import http from 'node:http';
import type { Server } from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sirv from 'sirv';

export const RAIZ = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
export const DIST = path.join(RAIZ, 'dist');

export function buscarChrome(): string | null {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const candidatos = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ];
  return candidatos.find((c) => fs.existsSync(c)) || null;
}

// Sirve dist/ como lo haría un hosting estático: primero el archivo real de cada
// ruta, y sólo si no existe, la portada.
export async function servirDist(puerto: number): Promise<Server> {
  const servir = sirv(DIST, { single: true, dev: true, extensions: ['html'] });
  const servidor = http.createServer((req: http.IncomingMessage, res: http.ServerResponse) =>
    servir(req, res, () => {
      res.statusCode = 404;
      res.end('No encontrado');
    }),
  );
  await new Promise<void>((r) => {
    servidor.listen(puerto, () => r());
  });
  return servidor;
}
