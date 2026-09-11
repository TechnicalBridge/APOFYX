/*
 * Cómo se calcula una cuota en DataBridge.
 *
 * El esquema es a propósito simple, y esa simpleza es parte de lo que la empresa
 * vende: el precio se fija en UF y el saldo se divide en cuotas iguales, sin
 * interés. La UF ya reajusta por inflación, así que agregarle una tasa encima
 * sería cobrar dos veces por lo mismo.
 *
 * Consecuencia práctica: pagar anticipado no tiene castigo ni premio en plata —
 * sólo adelanta la escritura. Por eso la respuesta a «¿puedo pagar antes?» en las
 * preguntas frecuentes puede ser un sí sin letra chica.
 *
 * El interés aparece en un solo lugar, la mora, y es el interés corriente que fija
 * el regulador. Eso no se calcula acá porque no es parte de cotizar una compra.
 */

/**
 * Valor de la UF en pesos.
 *
 * En producción esto lo entrega el backend, que lo toma del Banco Central: la UF
 * cambia todos los días. Acá queda fijo para que el sitio funcione solo y para que
 * el cotizador dé siempre el mismo número en una demostración.
 */
export const UF_EN_PESOS = 39_850;

/** Fecha del valor de arriba, para poder decirlo en pantalla en vez de esconderlo. */
export const UF_FECHA = 'septiembre de 2026';

/** El pie es el 20%, y también se puede pagar en cuotas. */
export const PIE_MINIMO = 0.2;

/** Los plazos que ofrece la empresa. Un proyecto puede permitir menos, nunca más. */
export const PLAZOS = [36, 48, 60] as const;

export interface Cotizacion {
  precioUF: number;
  pieUF: number;
  saldoUF: number;
  meses: number;
  cuotaUF: number;
  cuotaEnPesos: number;
  pieEnPesos: number;
}

export interface Consulta {
  precioUF: number;
  /** Fracción, no porcentaje: 0.2 es el 20%. */
  pie?: number;
  meses: number;
}

/**
 * Cuota de una compra con financiamiento directo.
 *
 * Devuelve la cuota en UF y su equivalente en pesos de hoy. El equivalente es
 * referencial y el sitio lo dice: lo que queda escrito en la promesa es la UF, y
 * el peso de la cuota número sesenta no es el de ahora.
 */
export function cotizar({ precioUF, pie = PIE_MINIMO, meses }: Consulta): Cotizacion {
  const pieUF = precioUF * pie;
  const saldoUF = precioUF - pieUF;
  // Un plazo de cero meses no existe en el formulario, pero dividir por cero acá
  // devolvería Infinity y lo pintaríamos en pantalla como si fuera un precio.
  const cuotaUF = meses > 0 ? saldoUF / meses : saldoUF;

  return {
    precioUF,
    pieUF,
    saldoUF,
    meses,
    cuotaUF,
    cuotaEnPesos: Math.round(cuotaUF * UF_EN_PESOS),
    pieEnPesos: Math.round(pieUF * UF_EN_PESOS),
  };
}

const UF = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 0 });
const UF_DECIMAL = new Intl.NumberFormat('es-CL', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const PESOS = new Intl.NumberFormat('es-CL', {
  style: 'currency',
  currency: 'CLP',
  maximumFractionDigits: 0,
});

/** Montos grandes en UF van sin decimales; una cuota chica los necesita. */
export const enUF = (valor: number) =>
  `UF ${valor >= 100 ? UF.format(Math.round(valor)) : UF_DECIMAL.format(valor)}`;

export const enPesos = (valor: number) => PESOS.format(valor);
