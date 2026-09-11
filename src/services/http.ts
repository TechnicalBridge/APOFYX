/*
 * El cliente HTTP contra el gateway.
 *
 * Todo lo que salga del navegador hacia el backend pasa por acá: un solo lugar
 * donde vive el origen, la forma de los errores y —cuando exista— el token.
 *
 * POR QUÉ UN GATEWAY Y NO CADA SERVICIO
 * El backend se parte en varios servicios, pero el frontend conoce un solo origen.
 * Si la UI llamara a cada servicio por su cuenta, partir `cartera` en dos mañana
 * obligaría a tocar componentes, y CORS habría que resolverlo seis veces. Con el
 * gateway adelante, la topología del backend no se filtra a la pantalla.
 *
 * MIENTRAS NO HAYA BACKEND
 * `VITE_API_URL` no está definida, y eso no es un error: el sitio todavía funciona
 * con contenido estático. Cada servicio decide qué hacer en ese caso —normalmente
 * devolver datos de ejemplo—, en vez de romper la página.
 */

const ORIGEN = import.meta.env['VITE_API_URL'] ?? '';

export const hayBackend = () => ORIGEN !== '';

export class ErrorDeApi extends Error {
  constructor(
    message: string,
    readonly estado: number,
  ) {
    super(message);
    this.name = 'ErrorDeApi';
  }
}

interface Opciones {
  metodo?: 'GET' | 'POST';
  cuerpo?: unknown;
  /** Para cancelar si el componente se desmonta antes de que responda. */
  senal?: AbortSignal;
}

export async function pedir<T>(ruta: string, { metodo = 'GET', cuerpo, senal }: Opciones = {}) {
  if (!hayBackend()) {
    throw new ErrorDeApi('No hay backend configurado (VITE_API_URL)', 0);
  }

  const respuesta = await fetch(`${ORIGEN}${ruta}`, {
    method: metodo,
    headers: cuerpo ? { 'Content-Type': 'application/json' } : undefined,
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    signal: senal,
  });

  if (!respuesta.ok) {
    // El cuerpo de un error puede venir vacío o no ser JSON; nunca hay que
    // dejar que eso tape el código de estado, que es la información útil.
    const detalle = await respuesta.text().catch(() => '');
    throw new ErrorDeApi(detalle || respuesta.statusText, respuesta.status);
  }

  return (await respuesta.json()) as T;
}
