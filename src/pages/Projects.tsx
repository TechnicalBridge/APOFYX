import PageHead from '../ui/PageHead';
import ProjectCard from '../ui/ProjectCard';
import Cta from '../sections/Cta';
import { retraso } from '../ui/Section';
import useInView from '../hooks/useInView';
import { getProyectos } from '../services/content';
import { ETIQUETA_ESTADO, type EstadoProyecto, type Proyecto } from '../domain/projects';
import useMeta from '../hooks/useMeta';

/*
 * El listado completo.
 *
 * Agrupado por estado en vez de filtrado. Con seis proyectos un filtro sería un
 * control que hay que accionar para ver lo que cabe entero en la pantalla; el
 * agrupamiento muestra todo y además responde la pregunta que el filtro haría
 * escribir: qué se puede comprar ahora y qué no.
 *
 * Los entregados se quedan en la página aunque no se vendan. Son el historial de la
 * empresa, y en un rubro donde cualquiera puede abrir una inmobiliaria el mes
 * pasado, mostrar lo terminado vale más que lo que está por venir.
 */

const ORDEN: EstadoProyecto[] = ['en-venta', 'en-construccion', 'proximamente', 'entregado'];

const NOTA: Partial<Record<EstadoProyecto, string>> = {
  'en-construccion': 'Con obra en marcha y fecha de entrega comprometida por contrato.',
  proximamente: 'Todavía no se venden. Se puede anotar en la lista de espera, nada más.',
  entregado: 'Proyectos terminados y habitados. Se pueden visitar.',
};

function Grupo({ estado, proyectos }: { estado: EstadoProyecto; proyectos: Proyecto[] }) {
  const [ref, visible] = useInView<HTMLElement>();

  return (
    <section className={`db-section db-grupo${visible ? ' db-revealed' : ''}`} ref={ref}>
      <div className="db-container">
        <header className="db-grupo-cabeza db-reveal">
          <h2 className="db-title-2">{ETIQUETA_ESTADO[estado]}</h2>
          <span className="db-grupo-cuenta db-cifra">
            {proyectos.length} {proyectos.length === 1 ? 'proyecto' : 'proyectos'}
          </span>
        </header>
        {NOTA[estado] && (
          <p className="db-note db-grupo-nota db-reveal" style={retraso(0, 60)}>
            {NOTA[estado]}
          </p>
        )}

        <div className="db-proyectos">
          {proyectos.map((p, i) => (
            <div className="db-reveal" key={p.slug} style={retraso(i, 120)}>
              <ProjectCard proyecto={p} />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function Projects() {
  useMeta({
    titulo: 'Proyectos',
    descripcion:
      'Seis desarrollos en San Clemente, Linares, Cauquenes y Chillán: parcelas de agrado, sitios urbanizados, casas y departamentos.',
  });

  const proyectos = getProyectos();
  const grupos = ORDEN.map((estado) => ({
    estado,
    proyectos: proyectos.filter((p) => p.estado === estado),
  })).filter((g) => g.proyectos.length > 0);

  const enVenta = proyectos.filter((p) => p.estado === 'en-venta');
  const unidades = enVenta.reduce((total, p) => total + p.disponibles, 0);

  return (
    <>
      <PageHead
        rotulo="Proyectos"
        titulo="Seis desarrollos, cuatro comunas."
        bajada="Parcelas de agrado, sitios urbanizados, casas y un edificio, entre el Maule y Ñuble. Todos con financiamiento directo salvo donde se indique."
      >
        <p className="db-note">
          {unidades} unidades disponibles ahora mismo en {enVenta.length} proyectos en venta.
        </p>
      </PageHead>

      {grupos.map((g) => (
        <Grupo key={g.estado} estado={g.estado} proyectos={g.proyectos} />
      ))}

      <Cta
        titulo="¿Ninguno calza?"
        bajada="Cuéntanos qué buscas —comuna, superficie, cuota máxima— y te avisamos cuando abramos algo que sirva. No mandamos nada más que eso."
      />
    </>
  );
}
