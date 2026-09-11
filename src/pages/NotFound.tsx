import { Link } from 'react-router-dom';

import PageHead from '../ui/PageHead';
import ProjectCard from '../ui/ProjectCard';
import { retraso } from '../ui/Section';
import { getDisponibles } from '../services/content';
import useMeta from '../hooks/useMeta';

/*
 * La página que no existe.
 *
 * En vez de un callejón sin salida muestra lo que sí se puede comprar. Quien llega
 * acá casi siempre venía siguiendo un enlace a un proyecto —de un aviso viejo, de
 * un mensaje reenviado—, así que lo útil es enseñarle el catálogo actual.
 */
export default function NotFound() {
  useMeta({
    titulo: 'Página no encontrada',
    descripcion: 'Esa dirección no existe. Revisa los proyectos disponibles hoy.',
  });

  const proyectos = getDisponibles();

  return (
    <>
      <PageHead
        rotulo="Página no encontrada"
        titulo="Esa dirección no existe."
        bajada="Puede que el enlace esté mal escrito o que apunte a un proyecto que ya no publicamos. Esto es lo que hay disponible hoy."
      >
        <Link className="db-btn db-btn-primary" to="/">
          Ir a la portada
        </Link>
      </PageHead>

      <section className="db-section db-revealed">
        <div className="db-container">
          <div className="db-proyectos">
            {proyectos.map((p, i) => (
              <div className="db-reveal" key={p.slug} style={retraso(i, 100)}>
                <ProjectCard proyecto={p} />
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
