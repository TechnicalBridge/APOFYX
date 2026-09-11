import type { ReactNode } from 'react';

import useInView from '../hooks/useInView';

/*
 * Envoltorio de cada sección de la portada.
 *
 * Hace dos cosas: da el andamiaje común —rótulo, título, bajada— y enciende la
 * entrada cuando la sección llega a la vista. El `db-revealed` que pone acá es el que
 * destraba todos los `.db-reveal` que haya adentro, así que una sección anima como
 * una unidad en vez de que cada hijo decida por su cuenta.
 */

interface Props {
  rotulo: string;
  titulo: string;
  bajada?: string;
  /** Para enlazar desde el nav o desde otra página. */
  id?: string;
  children: ReactNode;
}

export default function Section({ rotulo, titulo, bajada, id, children }: Props) {
  const [ref, visible] = useInView<HTMLElement>();

  return (
    <section className={`db-section${visible ? ' db-revealed' : ''}`} id={id} ref={ref}>
      <div className="db-container">
        <header className="db-section-head">
          <p className="db-eyebrow db-reveal">{rotulo}</p>
          <h2 className="db-title db-reveal" style={{ '--retraso': '70ms' } as React.CSSProperties}>
            {titulo}
          </h2>
          {bajada && (
            <p
              className="db-lede db-reveal"
              style={{ '--retraso': '140ms' } as React.CSSProperties}
            >
              {bajada}
            </p>
          )}
        </header>
        {children}
      </div>
    </section>
  );
}

/** Los componentes escalonan sus hijos con esto en vez de una clase por índice. */
export const retraso = (i: number, base = 200) =>
  ({ '--retraso': `${base + i * 80}ms` }) as React.CSSProperties;
