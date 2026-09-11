import type { ReactNode } from 'react';

/*
 * La cabecera de una página interior.
 *
 * Las siete páginas internas abrían con el mismo bloque copiado —rótulo, título,
 * bajada y el escalonado a mano en cada una—, que es justo el tipo de repetición
 * que se desincroniza cuando alguien ajusta un retraso en una sola.
 */

interface Props {
  /** Admite marcado porque las fichas cuelgan de acá su enlace al listado. */
  rotulo: ReactNode;
  titulo: string;
  bajada?: string;
  /** Datos o acciones que la página quiera colgar bajo la bajada. */
  children?: ReactNode;
}

const paso = (ms: number) => ({ '--retraso': `${ms}ms` }) as React.CSSProperties;

export default function PageHead({ rotulo, titulo, bajada, children }: Props) {
  return (
    <section className="db-page-head">
      <div className="db-container">
        <p className="db-eyebrow db-stagger">{rotulo}</p>
        <h1 className="db-title db-stagger" style={paso(70)}>
          {titulo}
        </h1>
        {bajada && (
          <p className="db-lede db-stagger" style={paso(140)}>
            {bajada}
          </p>
        )}
        {children && (
          <div className="db-page-head-extra db-stagger" style={paso(210)}>
            {children}
          </div>
        )}
      </div>
    </section>
  );
}
