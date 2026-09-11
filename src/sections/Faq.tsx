import { useState } from 'react';

import Section, { retraso } from '../ui/Section';
import { getPreguntas } from '../services/content';

/*
 * Las preguntas que se hacen antes de firmar.
 *
 * La primera abierta por defecto es la del crédito hipotecario, porque es la que
 * trae a la mayoría: alguien que ya fue rechazado por un banco llega buscando
 * exactamente eso. La que pregunta qué pasa si un mes no se puede pagar está
 * incluida aunque incomode — esconderla sólo la traslada al mes 14.
 */
export default function Faq() {
  const [abierta, setAbierta] = useState(0);
  const preguntas = getPreguntas();

  return (
    <Section rotulo="Preguntas" titulo="Lo que se pregunta antes de firmar.">
      <div className="db-faq">
        {preguntas.map((p, i) => {
          const activa = abierta === i;
          return (
            <div
              className={`db-faq-item db-reveal${activa ? ' db-faq-open' : ''}`}
              key={p.pregunta}
              style={retraso(i, 100)}
            >
              <h3>
                <button
                  type="button"
                  className="db-faq-btn"
                  aria-expanded={activa}
                  onClick={() => setAbierta(activa ? -1 : i)}
                >
                  <span>{p.pregunta}</span>
                  <svg className="db-chevron" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path
                      d="M6 9l6 6 6-6"
                      stroke="currentColor"
                      strokeWidth="1.75"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
              </h3>
              <div className="db-faq-answer" hidden={!activa}>
                <p>{p.respuesta}</p>
              </div>
            </div>
          );
        })}
      </div>
    </Section>
  );
}
