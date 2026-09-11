import Section, { retraso } from '../ui/Section';
import { getRazones } from '../services/content';

/*
 * Las tres razones para comprarle a esta inmobiliaria y no a otra.
 *
 * Van en este orden a propósito: primero cómo se elige el terreno (lo que el
 * comprador no puede verificar solo), después cómo se paga (lo que lo deja entrar),
 * y al final la escritura (lo que más miedo da en una compra a cinco años).
 */
export default function Reasons() {
  const razones = getRazones();

  return (
    <Section
      rotulo="Por qué nosotros"
      titulo="Vendemos suelo, pero lo que se compra es un plazo."
      bajada="Una parcela pagada en sesenta cuotas es una relación de cinco años con quien te la vendió. Estas son las tres cosas que definen cómo va a ser."
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
  );
}
