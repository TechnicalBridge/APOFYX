import Section, { retraso } from '../ui/Section';
import { getTestimonios } from '../services/content';

/*
 * Lo que dicen tres compradores.
 *
 * El del medio cuenta que se atrasó cuatro meses. Va a propósito: un testimonial
 * donde todo salió bien no prueba nada sobre una compra a cinco años, y lo que esta
 * empresa promete no es que nunca pase nada, sino qué hace cuando pasa.
 */
export default function Testimonials() {
  const testimonios = getTestimonios();

  return (
    <Section
      rotulo="Compradores"
      titulo="Cinco años es mucho tiempo para confiar en un folleto."
      bajada="Personas ficticias, como todo en este sitio. Las situaciones que describen sí son las que aparecen de verdad cuando se financia directo."
    >
      <div className="db-citas">
        {testimonios.map((t, i) => (
          <figure className="db-cita db-reveal" key={t.persona} style={retraso(i, 120)}>
            <blockquote>
              <p>{t.cita}</p>
            </blockquote>
            <figcaption>
              <span className="db-cita-persona">{t.persona}</span>
              <span className="db-note">
                {t.lugar} · {t.proyecto}
              </span>
            </figcaption>
          </figure>
        ))}
      </div>
    </Section>
  );
}
