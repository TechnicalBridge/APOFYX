import { Link } from 'react-router-dom';

import Photo from '../ui/Photo';
import { getEmpresa, getDestacado, getProyectos } from '../services/content';
import { enUF } from '../domain/financing';
import { ETIQUETA_ESTADO } from '../domain/projects';

/*
 * La portada.
 *
 * Abre a sangre con la vista aérea del proyecto destacado y la promesa encima. Es
 * la forma en que este rubro se presenta y tiene una razón: lo primero que decide
 * una compra de suelo es el lugar, y un titular sobre fondo blanco no muestra
 * ningún lugar.
 *
 * El paño es del proyecto destacado, pero el texto es de la empresa: quien llega a
 * una inmobiliaria con seis desarrollos todavía no eligió cuál. Por eso el
 * destacado aparece abajo como una tarjeta que se puede seguir, y no como el tema
 * del encabezado.
 *
 * Los datos de la fila inferior son de la empresa entera y salen del dominio —el
 * precio más bajo y la cantidad de comunas se recalculan solos cuando cambia el
 * catálogo, en vez de quedar escritos a mano y envejecer.
 */

const paso = (ms: number) => ({ '--retraso': `${ms}ms` }) as React.CSSProperties;

export default function Hero() {
  const empresa = getEmpresa();
  const destacado = getDestacado();
  const proyectos = getProyectos();

  const desde = Math.min(...proyectos.map((p) => p.desdeUF));
  const comunas = new Set(proyectos.map((p) => p.comuna)).size;

  const datos: [string, string][] = [
    ['Desde', enUF(desde)],
    ['Cuotas', 'Fijas en UF, sin interés'],
    ['Plazo', '36 a 60 meses'],
    ['Dónde', `${comunas} comunas del Maule y Ñuble`],
  ];

  return (
    <section className="db-hero">
      <div className="db-hero-fondo" aria-hidden="true">
        <Photo archivo={destacado.fotos[0]!.archivo} alt="" llenar prioridad />
      </div>

      <div className="db-container db-hero-contenido">
        <p className="db-hero-rotulo db-stagger">
          {empresa.rubro} · {destacado.region}
        </p>

        <h1 className="db-title-hero db-stagger" style={paso(70)}>
          {empresa.promesa}
        </h1>

        <p className="db-hero-bajada db-stagger" style={paso(140)}>
          {empresa.bajada}
        </p>

        <div className="db-hero-actions db-stagger" style={paso(210)}>
          <Link className="db-btn db-btn-primary" to="/proyectos">
            Ver proyectos
          </Link>
          <Link className="db-btn db-btn-fantasma" to="/financiamiento">
            Calcular una cuota
          </Link>
        </div>

        <dl className="db-hero-datos db-stagger" style={paso(280)}>
          {datos.map(([etiqueta, valor]) => (
            <div key={etiqueta}>
              <dt>{etiqueta}</dt>
              <dd className="db-cifra">{valor}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="db-container">
        <Link
          className="db-hero-destacado db-stagger"
          to={`/proyectos/${destacado.slug}`}
          style={paso(350)}
        >
          <span className="db-hero-destacado-vista">
            <Photo
              archivo={destacado.fotos[destacado.fotos.length - 1]!.archivo}
              alt=""
              proporcion="16 / 10"
            />
          </span>
          <span className="db-hero-destacado-texto">
            <span className="db-eyebrow">Proyecto destacado</span>
            <strong>{destacado.nombre}</strong>
            <span className="db-note">
              {destacado.comuna} · {destacado.superficie} · desde {enUF(destacado.desdeUF)}
            </span>
          </span>
          <span className="db-hero-destacado-cifra">
            <span className="db-badge db-badge-ok">{ETIQUETA_ESTADO[destacado.estado]}</span>
            <span className="db-cifra">
              {destacado.disponibles}
              <span className="db-de-total"> de {destacado.unidades} disponibles</span>
            </span>
          </span>
        </Link>
      </div>
    </section>
  );
}
