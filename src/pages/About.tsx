import PageHead from '../ui/PageHead';
import Section, { retraso } from '../ui/Section';
import Stats from '../sections/Stats';
import Cta from '../sections/Cta';
import { getHitos, getRazones, getEmpresa } from '../services/content';
import useMeta from '../hooks/useMeta';

/*
 * Quiénes somos.
 *
 * La historia explica el nombre —la empresa partió tasando suelo, no construyendo—
 * y explica por qué financia: el banco rechazaba compradores que sí podían pagar.
 * Las dos cosas son la misma decisión vista a diez años de distancia, y por eso la
 * línea de tiempo va antes que cualquier declaración de valores.
 */
export default function About() {
  useMeta({
    titulo: 'Nosotros',
    descripcion:
      'Doce años en el Maule: partimos tasando suelo para otros en 2014 y hoy desarrollamos y financiamos nuestros propios proyectos.',
  });

  const empresa = getEmpresa();
  const hitos = getHitos();
  const razones = getRazones();

  return (
    <>
      <PageHead
        rotulo="Nosotros"
        titulo="Empezamos diciéndole a la gente dónde no comprar."
        bajada={empresa.origen}
      />

      <Section
        rotulo="Historia"
        titulo="Doce años, en orden."
        bajada="De una oficina de tasación a nueve proyectos desarrollados. El cambio que más pesó no fue construir: fue empezar a dar el crédito nosotros."
      >
        <ol className="db-linea">
          {hitos.map((h, i) => (
            <li className="db-hito db-reveal" key={h.ano} style={retraso(i, 110)}>
              <div className="db-hito-marca">
                <span className="db-hito-ano db-cifra">{h.ano}</span>
                {i < hitos.length - 1 && <span className="db-hito-linea" aria-hidden="true" />}
              </div>
              <div className="db-hito-texto">
                <h3 className="db-title-2">{h.titulo}</h3>
                <p>{h.cuerpo}</p>
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <Stats />

      <Section
        rotulo="Cómo trabajamos"
        titulo="Tres cosas que no negociamos."
        bajada="No son valores de folleto: son las tres reglas que más veces nos han costado una venta."
      >
        <div className="db-razones">
          {razones.map((r, i) => (
            <article className="db-razon db-reveal" key={r.clave} style={retraso(i)}>
              <span className="db-razon-n db-cifra">{String(i + 1).padStart(2, '0')}</span>
              <h3 className="db-title-2">{r.titulo}</h3>
              <p className="db-razon-bajada">{r.bajada}</p>
              <p>{r.cuerpo}</p>
            </article>
          ))}
        </div>
      </Section>

      <Section rotulo="Dónde estamos" titulo="La oficina.">
        <div className="db-oficina db-reveal">
          <div>
            <h3 className="db-title-2">{empresa.nombre}</h3>
            <address>
              {empresa.direccion}
              <br />
              {empresa.comuna}
            </address>
            <p className="db-note">{empresa.horario}</p>
          </div>
          <dl className="db-oficina-datos">
            <div>
              <dt>Teléfono</dt>
              <dd className="db-cifra">
                <a href={`tel:${empresa.telefono.replace(/\s/g, '')}`}>{empresa.telefono}</a>
              </dd>
            </div>
            <div>
              <dt>Ventas</dt>
              <dd>
                <a href={`mailto:${empresa.correoVentas}`}>{empresa.correoVentas}</a>
              </dd>
            </div>
            <div>
              <dt>Administración</dt>
              <dd>
                <a href={`mailto:${empresa.correo}`}>{empresa.correo}</a>
              </dd>
            </div>
          </dl>
        </div>
      </Section>

      <Cta />
    </>
  );
}
