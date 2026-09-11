import PageHead from '../ui/PageHead';
import Photo from '../ui/Photo';
import useMeta from '../hooks/useMeta';
import { CREDITOS, URL_LICENCIAS } from '../domain/photo-credits';
import { findProyecto } from '../services/content';

/*
 * De dónde salen las fotos.
 *
 * Existe por una razón legal concreta: las imágenes están bajo licencias Creative
 * Commons que permiten usarlas y modificarlas a cambio de nombrar al autor. Esta
 * es esa atribución, junto en un lugar en vez de repartida sobre las fotos.
 *
 * Muestra la miniatura al lado de cada crédito para que se pueda comprobar cuál es
 * cuál sin tener que abrir el archivo.
 */
export default function Credits() {
  useMeta({
    titulo: 'Créditos fotográficos',
    descripcion:
      'Autoría y licencias de las fotografías usadas en el sitio, todas bajo Creative Commons.',
  });

  return (
    <>
      <PageHead
        rotulo="Créditos"
        titulo="De dónde salen las fotos."
        bajada="Las imágenes son de sus autores y están publicadas bajo licencias Creative Commons que permiten reutilizarlas y modificarlas nombrando a quien las hizo. Acá están todas."
      />

      <section className="db-section">
        <div className="db-container">
          <ul className="db-creditos">
            {CREDITOS.map((c) => {
              const slug = c.archivo.replace(/-\d+\.jpg$/, '');
              const proyecto = findProyecto(slug);
              return (
                <li className="db-credito" key={c.archivo}>
                  <Photo
                    archivo={c.archivo}
                    alt=""
                    proporcion="3 / 2"
                    className="db-credito-mini"
                  />
                  <div>
                    <p className="db-credito-titulo">{c.titulo}</p>
                    <p className="db-note">
                      {c.autor} ·{' '}
                      <a href={URL_LICENCIAS[c.licencia] ?? 'https://creativecommons.org/'}>
                        CC {c.licencia}
                      </a>{' '}
                      · <a href={c.origen}>ver original</a>
                    </p>
                    {proyecto && <p className="db-note">Usada en {proyecto.nombre}</p>}
                  </div>
                </li>
              );
            })}
          </ul>

          <p className="db-aviso">
            Las fotografías ilustran proyectos inventados: no son de los terrenos ni de las comunas
            que el sitio menciona, porque esos proyectos no existen. Se recortaron y reescalaron,
            que es algo que estas licencias permiten.
          </p>
        </div>
      </section>
    </>
  );
}
