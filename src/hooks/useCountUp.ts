import { useEffect, useState } from 'react';

/*
 * Cuenta de 0 al destino cuando `activo` se enciende.
 *
 * La curva es easeOutCubic: rápido al principio y frenando al final, que es como
 * se lee un contador real. Una curva lineal se ve mecánica y una con rebote miente
 * sobre el dato.
 *
 * Con `prefers-reduced-motion` no cuenta: muestra el número final y listo. La cifra
 * es el contenido; la animación es sólo la forma de llegar.
 */

const MS_POR_DEFECTO = 1100;

const menosMovimiento = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export default function useCountUp(destino: number, activo: boolean, ms = MS_POR_DEFECTO) {
  const [valor, setValor] = useState(0);

  useEffect(() => {
    if (!activo) return undefined;

    if (menosMovimiento()) {
      setValor(destino);
      return undefined;
    }

    let cuadro = 0;
    let inicio: number | null = null;

    const paso = (t: number) => {
      if (inicio === null) inicio = t;
      const avance = Math.min((t - inicio) / ms, 1);
      const suave = 1 - (1 - avance) ** 3;
      setValor(Math.round(destino * suave));
      if (avance < 1) cuadro = requestAnimationFrame(paso);
    };

    cuadro = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(cuadro);
  }, [destino, activo, ms]);

  return valor;
}
