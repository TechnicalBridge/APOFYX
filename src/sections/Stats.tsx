import Section, { retraso } from '../ui/Section';
import useCountUp from '../hooks/useCountUp';
import useInView from '../hooks/useInView';
import { getCifras, type Cifra } from '../services/content';

/*
 * Las cifras de la empresa.
 *
 * La última —cuántos compradores están pagando hoy— es la que de verdad describe
 * el negocio: una inmobiliaria que vende con hipotecario cobra una vez y se olvida,
 * y esta se queda con la cartera. Por eso va al final, que es donde queda la vista.
 */

function Numero({ cifra, activo }: { cifra: Cifra; activo: boolean }) {
  const valor = useCountUp(cifra.valor, activo);
  return (
    <span className="db-stat-n db-cifra">
      {valor.toLocaleString('es-CL')}
      {cifra.sufijo}
    </span>
  );
}

export default function Stats() {
  // La sección ya tiene su propio observador para la entrada; los contadores
  // necesitan otro porque arrancan cuando la grilla —no la cabecera— está a la vista.
  const [ref, visible] = useInView<HTMLDivElement>({ umbral: 0.3 });

  return (
    <Section
      rotulo="La empresa"
      titulo="Doce años eligiendo dónde no comprar."
      bajada="Cifras de un proyecto académico: la empresa es ficticia y los números son ilustrativos."
    >
      <div className="db-stats" ref={ref}>
        {getCifras().map((c, i) => (
          <div className="db-stat db-reveal" key={c.etiqueta} style={retraso(i)}>
            <Numero cifra={c} activo={visible} />
            <p className="db-stat-label">{c.etiqueta}</p>
            <p className="db-note">{c.detalle}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}
