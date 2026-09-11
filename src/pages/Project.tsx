import { Link, useParams } from 'react-router-dom';

import PageHead from '../ui/PageHead';
import SitePlan from '../ui/SitePlan';
import Photo from '../ui/Photo';
import Gallery from '../ui/Gallery';
import Quote from '../ui/Quote';
import Section, { retraso } from '../ui/Section';
import Cta from '../sections/Cta';
import { findProyecto, getEmpresa } from '../services/content';
import { ETIQUETA_ESTADO, ETIQUETA_TIPO } from '../domain/projects';
import { enUF } from '../domain/financing';
import useMeta from '../hooks/useMeta';

/*
 * La ficha de un proyecto.
 *
 * El orden responde a cómo se decide una compra de suelo: primero dónde y cuánto
 * mide, después qué está hecho y qué no, y recién al final cuánto sale la cuota.
 * El cotizador va abajo a propósito —quien llega a calcular una cuota ya decidió
 * que el terreno le interesa— y arriba queda la ficha técnica, que es lo que se
 * compara entre proyectos.
 *
 * La lista de atributos no está redactada para vender: dice «dos kilómetros de
 * ripio» donde otro folleto diría «acceso expedito». Es la misma decisión que
 * atraviesa todo el sitio.
 */

export default function Project() {
  const { slug } = useParams();
  const proyecto = slug ? findProyecto(slug) : undefined;
  const empresa = getEmpresa();

  // Va antes del retorno temprano porque los hooks no admiten condicionales, y de
  // paso hace que la ficha inexistente también traiga su propio título.
  useMeta({
    titulo: proyecto ? proyecto.nombre : 'Proyecto no encontrado',
    descripcion: proyecto
      ? `${ETIQUETA_TIPO[proyecto.tipo]} en ${proyecto.comuna}. ${proyecto.resumen} Desde ${enUF(proyecto.desdeUF)} con financiamiento directo hasta ${proyecto.plazoMaximo} meses.`
      : 'Ese proyecto no está publicado. Revisa el listado completo.',
  });

  // Un slug inventado en la barra de direcciones no puede terminar en una página
  // en blanco: se dice qué pasó y se ofrece la salida.
  if (!proyecto) {
    return (
      <>
        <PageHead
          rotulo="Proyecto"
          titulo="No encontramos ese proyecto."
          bajada="Puede que la dirección esté mal escrita o que el proyecto ya no esté publicado."
        >
          <Link className="db-btn db-btn-primary" to="/proyectos">
            Ver todos los proyectos
          </Link>
        </PageHead>
      </>
    );
  }

  const vendidas = proyecto.unidades - proyecto.disponibles;
  const enVenta = proyecto.estado === 'en-venta' || proyecto.estado === 'en-construccion';

  const ficha: [string, string][] = [
    ['Tipo', ETIQUETA_TIPO[proyecto.tipo]],
    ['Comuna', `${proyecto.comuna}, ${proyecto.region}`],
    ['Superficie', proyecto.superficie],
    ['Precio desde', enUF(proyecto.desdeUF)],
    ['Unidades', `${proyecto.unidades} en total`],
    ['Disponibles', `${proyecto.disponibles} (${vendidas} vendidas)`],
    ['Entrega', proyecto.entrega],
    ['Financiamiento directo', `Hasta ${proyecto.plazoMaximo} meses`],
  ];

  return (
    <>
      {/* La portada del proyecto es el paño, a sangre: lo primero que decide una
          compra de suelo es el lugar, y para eso hay que mostrarlo. */}
      <section className="db-ficha-portada">
        <div className="db-ficha-portada-fondo" aria-hidden="true">
          <Photo archivo={proyecto.fotos[0]!.archivo} alt="" llenar prioridad />
        </div>

        <div className="db-container db-ficha-portada-texto">
          <p className="db-hero-rotulo db-stagger">
            <Link to="/proyectos">Proyectos</Link> · {proyecto.comuna}, {proyecto.region}
          </p>
          <h1
            className="db-title-hero db-stagger"
            style={{ '--retraso': '70ms' } as React.CSSProperties}
          >
            {proyecto.nombre}
          </h1>
          <p
            className="db-hero-bajada db-stagger"
            style={{ '--retraso': '140ms' } as React.CSSProperties}
          >
            {proyecto.resumen}
          </p>

          <dl
            className="db-hero-datos db-stagger"
            style={{ '--retraso': '210ms' } as React.CSSProperties}
          >
            <div>
              <dt>Superficie</dt>
              <dd className="db-cifra">{proyecto.superficie}</dd>
            </div>
            <div>
              <dt>Desde</dt>
              <dd className="db-cifra">{enUF(proyecto.desdeUF)}</dd>
            </div>
            <div>
              <dt>Entrega</dt>
              <dd className="db-cifra">{proyecto.entrega}</dd>
            </div>
            {enVenta && (
              <div>
                <dt>Disponibles</dt>
                <dd className="db-cifra">
                  {proyecto.disponibles}
                  <span className="db-de-total"> de {proyecto.unidades}</span>
                </dd>
              </div>
            )}
          </dl>

          <div
            className="db-ficha-rotulos db-stagger"
            style={{ '--retraso': '280ms' } as React.CSSProperties}
          >
            <span className="db-badge db-badge-ok">{ETIQUETA_ESTADO[proyecto.estado]}</span>
            <span className="db-badge db-badge-neutral">{ETIQUETA_TIPO[proyecto.tipo]}</span>
          </div>
        </div>
      </section>

      <section className="db-section">
        <div className="db-container db-ficha">
          <div className="db-ficha-plano">
            <SitePlan proyecto={proyecto} />
            <p className="db-note">
              Los lotes pintados están vendidos y los vacíos disponibles. El plano aprobado, con
              medidas y deslindes, se entrega firmado junto con la promesa.
            </p>
          </div>

          <div className="db-ficha-datos">
            <h2 className="db-title-2">Ficha</h2>
            <dl className="db-ficha-tabla">
              {ficha.map(([etiqueta, valor]) => (
                <div key={etiqueta}>
                  <dt>{etiqueta}</dt>
                  <dd className="db-cifra">{valor}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>

      <Section rotulo="El proyecto" titulo="Qué es y dónde queda.">
        <div className="db-ficha-cuerpo">
          <div className="db-prosa db-reveal">
            {proyecto.descripcion.map((parrafo) => (
              <p key={parrafo.slice(0, 40)}>{parrafo}</p>
            ))}
          </div>

          <aside className="db-atributos db-reveal" style={retraso(1)}>
            <h3 className="db-title-2">Lo que está hecho</h3>
            <ul>
              {proyecto.atributos.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
            <p className="db-note">
              Si algo no aparece en esta lista, es porque no está. Cualquier duda se responde por
              teléfono al {empresa.telefono} antes de que reserves.
            </p>
          </aside>
        </div>
      </Section>

      <Section
        rotulo="El paño"
        titulo="Cómo se ve el terreno."
        bajada="El terreno, el entorno y el plano de loteo con lo que queda disponible."
      >
        <Gallery proyecto={proyecto} />
      </Section>

      {enVenta ? (
        <Section
          rotulo="Financiamiento"
          titulo="Cuánto queda la cuota."
          bajada={`${proyecto.nombre} se financia directo hasta ${proyecto.plazoMaximo} meses. Mueves el pie y el plazo y ves la cuota al instante, sin dejar datos.`}
        >
          <div className="db-reveal">
            <Quote proyecto={proyecto} />
          </div>
        </Section>
      ) : (
        <Section
          rotulo="Financiamiento"
          titulo="Este proyecto no está en venta."
          bajada={
            proyecto.estado === 'proximamente'
              ? 'No recibimos reservas ni pagos hasta que esté la recepción municipal. Puedes anotarte en la lista de espera y te avisamos cuando abra.'
              : 'Las unidades disponibles se venden directo en oficina. Escríbenos y coordinamos una visita.'
          }
        >
          <div className="db-reveal">
            <Link className="db-btn db-btn-primary" to="/contacto">
              {proyecto.estado === 'proximamente'
                ? 'Anotarme en la lista'
                : 'Consultar por una unidad'}
            </Link>
          </div>
        </Section>
      )}

      <Cta />
    </>
  );
}
