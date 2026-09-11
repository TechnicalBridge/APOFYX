import Photo from './Photo';
import SitePlan from './SitePlan';
import { retraso } from './Section';
import type { Proyecto } from '../domain/projects';

/*
 * Las vistas del proyecto: las fotos del paño y, al final, el plano de loteo.
 *
 * El plano cierra la galería a propósito. Las fotos responden «¿me gusta el
 * lugar?» y el plano responde «¿cuál lote me toca y cuáles quedan?», que es la
 * pregunta siguiente y la que un folleto suele dejar sin contestar. Además se
 * actualiza solo con la disponibilidad, así que nunca queda desfasado respecto de
 * la ficha.
 */

export default function Gallery({ proyecto }: { proyecto: Proyecto }) {
  return (
    <div className="db-galeria">
      {proyecto.fotos.map((f, i) => (
        <figure className="db-toma db-reveal" key={f.archivo} style={retraso(i, 110)}>
          <Photo archivo={f.archivo} alt={`${proyecto.nombre}: ${f.pie}`} proporcion="16 / 10" />
          <figcaption>{f.pie}</figcaption>
        </figure>
      ))}

      <figure
        className="db-toma db-toma-plano db-reveal"
        style={retraso(proyecto.fotos.length, 110)}
      >
        <SitePlan proyecto={proyecto} />
        <figcaption>
          Plano de loteo · {proyecto.disponibles} de {proyecto.unidades} disponibles
        </figcaption>
      </figure>
    </div>
  );
}
