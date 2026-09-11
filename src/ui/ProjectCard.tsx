import { Link } from 'react-router-dom';

import Photo from './Photo';
import { ETIQUETA_ESTADO, ETIQUETA_TIPO, type Proyecto } from '../domain/projects';
import { enUF } from '../domain/financing';

/*
 * La tarjeta de un proyecto en el listado.
 *
 * Muestra lo que se pregunta antes de entrar a la ficha: dónde queda, qué es,
 * desde cuánto y si todavía quedan unidades. La disponibilidad va con su número
 * exacto en vez de un «últimas unidades»: la escasez inventada es justo el recurso
 * que hace desconfiar de este rubro.
 */

const TONO_ESTADO: Record<Proyecto['estado'], string> = {
  'en-venta': 'db-badge-ok',
  'en-construccion': 'db-badge-info',
  entregado: 'db-badge-neutral',
  proximamente: 'db-badge-warn',
};

export default function ProjectCard({ proyecto }: { proyecto: Proyecto }) {
  const portada = proyecto.fotos[0]!;
  const agotado = proyecto.disponibles === 0;
  const porVender = proyecto.estado !== 'proximamente';

  return (
    <article className="db-proyecto">
      <Link className="db-proyecto-enlace" to={`/proyectos/${proyecto.slug}`}>
        <div className="db-proyecto-vista">
          <Photo
            archivo={portada.archivo}
            alt={`${proyecto.nombre}: ${portada.pie}`}
            proporcion="16 / 10"
          />
        </div>

        <div className="db-proyecto-cuerpo">
          <div className="db-proyecto-rotulos">
            <span className={`db-badge ${TONO_ESTADO[proyecto.estado]}`}>
              {ETIQUETA_ESTADO[proyecto.estado]}
            </span>
            <span className="db-proyecto-tipo">{ETIQUETA_TIPO[proyecto.tipo]}</span>
          </div>

          <h3 className="db-proyecto-nombre">{proyecto.nombre}</h3>
          <p className="db-proyecto-lugar">
            {proyecto.comuna}, {proyecto.region}
          </p>
          <p className="db-proyecto-resumen">{proyecto.resumen}</p>

          <dl className="db-proyecto-datos">
            <div>
              <dt>Desde</dt>
              <dd className="db-cifra">{enUF(proyecto.desdeUF)}</dd>
            </div>
            <div>
              <dt>Superficie</dt>
              <dd className="db-cifra">{proyecto.superficie}</dd>
            </div>
            <div>
              <dt>{porVender ? 'Disponibles' : 'Unidades'}</dt>
              <dd className="db-cifra">
                {porVender ? (
                  <>
                    {proyecto.disponibles}
                    <span className="db-de-total"> de {proyecto.unidades}</span>
                  </>
                ) : (
                  proyecto.unidades
                )}
              </dd>
            </div>
          </dl>

          {agotado && <p className="db-note">Sin unidades disponibles por ahora.</p>}
        </div>
      </Link>
    </article>
  );
}
