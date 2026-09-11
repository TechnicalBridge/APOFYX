import Section, { retraso } from '../ui/Section';
import { getPasos } from '../services/content';

/*
 * Los cuatro pasos de una compra, con su plazo.
 *
 * El plazo es lo que hace útil la lista. «Reserva, evaluación, promesa, escritura»
 * lo dice cualquiera; decir que la evaluación demora dos días hábiles y que la
 * escritura llega recién con la última cuota es lo que deja al comprador con una
 * expectativa correcta en vez de una agradable.
 */
export default function Steps() {
  const pasos = getPasos();

  return (
    <Section
      rotulo="Cómo se compra"
      titulo="De la reserva a la escritura."
      bajada="Cuatro pasos, cada uno con el tiempo que toma de verdad. No hay ninguno que se resuelva «a la brevedad»."
    >
      <ol className="db-pasos">
        {pasos.map((p, i) => (
          <li className="db-paso db-reveal" key={p.n} style={retraso(i)}>
            <div className="db-paso-marca">
              <span className="db-paso-n db-cifra">{p.n}</span>
              {i < pasos.length - 1 && <span className="db-paso-linea" aria-hidden="true" />}
            </div>
            <div className="db-paso-texto">
              <div className="db-paso-cabeza">
                <h3 className="db-title-2">{p.titulo}</h3>
                <span className="db-badge db-badge-neutral">{p.plazo}</span>
              </div>
              <p>{p.cuerpo}</p>
            </div>
          </li>
        ))}
      </ol>
    </Section>
  );
}
