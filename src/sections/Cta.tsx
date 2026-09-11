import { Link } from 'react-router-dom';

import { getEmpresa } from '../services/content';

/*
 * El cierre, reutilizado al final de casi todas las páginas.
 *
 * Antes vivía dentro de la sección de preguntas, lo que obligaba a arrastrar esa
 * sección entera para tener un cierre en otra página. Acá es una pieza suya, con
 * el texto parametrizable, y cada página decide con qué se despide.
 */

interface Props {
  titulo?: string;
  bajada?: string;
}

export default function Cta({ titulo, bajada }: Props) {
  const empresa = getEmpresa();

  return (
    <section className="db-cta">
      <div className="db-container db-cta-box">
        <h2 className="db-title">{titulo ?? 'Ven a ver el terreno antes de decidir.'}</h2>
        <p className="db-lede">
          {bajada ??
            'Coordinamos la visita cualquier día de semana o el sábado en la mañana. Se puede ir sin haber reservado nada.'}
        </p>
        <div className="db-hero-actions">
          <Link className="db-btn db-btn-primary" to="/contacto">
            Coordinar una visita
          </Link>
          <Link className="db-btn db-btn-secondary" to="/financiamiento">
            Calcular una cuota
          </Link>
        </div>
        <p className="db-note db-cta-nota">
          O escríbenos directo a{' '}
          <a href={`mailto:${empresa.correoVentas}`}>{empresa.correoVentas}</a> · {empresa.telefono}
        </p>
      </div>
    </section>
  );
}
