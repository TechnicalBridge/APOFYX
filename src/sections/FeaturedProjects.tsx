import { Link } from 'react-router-dom';

import Section, { retraso } from '../ui/Section';
import ProjectCard from '../ui/ProjectCard';
import { getDisponibles } from '../services/content';

/*
 * Los proyectos que se pueden comprar hoy.
 *
 * La portada muestra sólo los que están en venta o en construcción: llenar el
 * listado con proyectos entregados y con lo que todavía no tiene recepción
 * municipal infla el catálogo y deja al visitante entrando a fichas que no llevan a
 * ninguna parte. Los otros están en el listado completo, con su estado a la vista.
 */
export default function FeaturedProjects() {
  const proyectos = getDisponibles();

  return (
    <Section
      rotulo="Proyectos"
      titulo="Lo que se puede comprar hoy."
      bajada="Los desarrollos en venta y en construcción, entre el Maule y Ñuble. El número de unidades disponibles es el real de cada uno, no una cuenta regresiva."
    >
      <div className="db-proyectos">
        {proyectos.map((p, i) => (
          <div className="db-reveal" key={p.slug} style={retraso(i, 120)}>
            <ProjectCard proyecto={p} />
          </div>
        ))}
      </div>

      <p className="db-section-pie db-reveal" style={retraso(proyectos.length, 120)}>
        <Link className="db-enlace-fuerte" to="/proyectos">
          Ver todos los proyectos, incluidos los entregados →
        </Link>
      </p>
    </Section>
  );
}
