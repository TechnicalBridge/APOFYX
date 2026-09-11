import { useEffect, useRef, useState } from 'react';

/*
 * Devuelve [ref, visible]: `visible` pasa a true la primera vez que el elemento
 * entra en pantalla y ya no vuelve atrás.
 *
 * Es la base de todas las entradas del sitio. Dos decisiones deliberadas:
 *
 *  · Una sola vez. Animar cada vez que algo vuelve a entrar convierte el scroll en
 *    un parpadeo y cansa al tercer viaje.
 *
 *  · Si el visitante pidió menos movimiento, arranca en true. No es una versión
 *    degradada: es el mismo contenido, quieto y completo, desde el primer cuadro.
 */

interface Opciones {
  /** Cuánto del elemento tiene que asomar para contar como visible. */
  umbral?: number;
  /** Margen extra para que la entrada empiece justo antes de llegar al borde. */
  margen?: string;
}

const menosMovimiento = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export default function useInView<T extends HTMLElement = HTMLDivElement>({
  umbral = 0.15,
  margen = '0px 0px -10% 0px',
}: Opciones = {}) {
  const ref = useRef<T>(null);
  const [visible, setVisible] = useState(() => menosMovimiento());

  useEffect(() => {
    if (visible) return undefined;

    const nodo = ref.current;
    if (!nodo || typeof IntersectionObserver === 'undefined') {
      setVisible(true);
      return undefined;
    }

    const observador = new IntersectionObserver(
      (entradas) => {
        if (!entradas.some((e) => e.isIntersecting)) return;
        setVisible(true);
        observador.disconnect();
      },
      { threshold: umbral, rootMargin: margen },
    );

    observador.observe(nodo);
    return () => observador.disconnect();
  }, [visible, umbral, margen]);

  return [ref, visible] as const;
}
