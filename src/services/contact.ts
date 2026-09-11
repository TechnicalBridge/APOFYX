/*
 * Consultas por un proyecto.
 *
 * Del lado del backend esto no merece un servicio propio: es una escritura simple
 * contra la tabla de prospectos. Se separa acá porque el frontend sí tiene una
 * pantalla dedicada, y porque el día que haya captcha o límite de envíos, el cambio
 * queda contenido en este archivo.
 */
import { pedir, hayBackend } from './http';

export interface Consulta {
  nombre: string;
  email: string;
  telefono: string;
  /** Slug del proyecto, o vacío si todavía no eligió ninguno. */
  proyecto: string;
  mensaje?: string;
}

export type Envio = { estado: 'enviado' } | { estado: 'error'; motivo: string };

const CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/*
 * El teléfono se valida por cantidad de dígitos y no con una expresión estricta.
 * La gente lo escribe con +56, con paréntesis, con espacios o con guiones, y
 * rechazar un número correcto por su formato es la forma más tonta de perder una
 * consulta: lo importante es que haya un número al que llamar.
 */
const digitos = (v: string) => v.replace(/\D/g, '');

export function revisar(c: Consulta): Partial<Record<keyof Consulta, string>> {
  const fallos: Partial<Record<keyof Consulta, string>> = {};
  if (!c.nombre.trim()) fallos.nombre = 'Falta tu nombre.';
  if (!CORREO.test(c.email.trim())) fallos.email = 'Revisa el correo: no parece una dirección.';
  const n = digitos(c.telefono);
  if (n.length < 8) fallos.telefono = 'Déjanos un teléfono con al menos 8 dígitos.';
  return fallos;
}

export async function enviarConsulta(c: Consulta, senal?: AbortSignal): Promise<Envio> {
  if (!hayBackend()) {
    // Sin backend la pantalla igual completa su recorrido: es una demostración, y
    // una demostración que se queda a mitad de camino no demuestra nada.
    return { estado: 'enviado' };
  }
  try {
    await pedir('/api/consultas', { metodo: 'POST', cuerpo: c, senal });
    return { estado: 'enviado' };
  } catch {
    return { estado: 'error', motivo: 'No pudimos enviar la consulta. Escríbenos por correo.' };
  }
}
