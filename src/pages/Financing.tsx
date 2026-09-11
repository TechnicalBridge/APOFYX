import PageHead from '../ui/PageHead';
import Quote from '../ui/Quote';
import Section, { retraso } from '../ui/Section';
import Steps from '../sections/Steps';
import Faq from '../sections/Faq';
import Cta from '../sections/Cta';
import { getReglas, getEmpresa } from '../services/content';
import useMeta from '../hooks/useMeta';

/*
 * La página que explica cómo se paga.
 *
 * Es la más importante del sitio, porque es lo que diferencia a esta inmobiliaria:
 * financia ella misma. Y por eso incluye algo que ningún folleto del rubro trae —la
 * política de mora, con días exactos, en el sitio público y antes de firmar.
 *
 * La decisión de publicarla tiene una razón concreta: quien compra a sesenta cuotas
 * va a tener un mes malo en algún momento de esos cinco años. Saber de antemano que
 * hay diez días de gracia y que a los noventa se repacta antes de cualquier otra
 * cosa es información que cambia la decisión de compra. Esconderla hasta que pase
 * es lo que convierte un atraso en un conflicto.
 */
export default function Financing() {
  useMeta({
    titulo: 'Financiamiento directo',
    descripcion:
      'Cuotas iguales en UF, sin interés, de 36 a 60 meses y sin banco. Cotiza la cuota sin dejar datos y revisa qué pasa si te atrasas.',
  });

  const reglas = getReglas();
  const empresa = getEmpresa();

  return (
    <>
      <PageHead
        rotulo="Financiamiento"
        titulo="Te financiamos nosotros, no el banco."
        bajada="Cuotas iguales en UF, sin interés, de 36 a 60 meses. La evaluación mira lo que ganas, no lo que dice un registro de morosidad."
      />

      <Section
        rotulo="Cotizador"
        titulo="Mira la cuota antes de hablar con nadie."
        bajada="Elige proyecto, pie y plazo. No pide nombre, teléfono ni correo: si tienes que dejar tus datos para saber cuánto sale algo, ese precio no era un precio."
      >
        <div className="db-reveal">
          <Quote />
        </div>
      </Section>

      <Steps />

      <Section
        rotulo="Si te atrasas"
        titulo="Qué pasa el mes que no puedes pagar."
        bajada="Va acá, en el sitio público y antes de que firmes, porque en cinco años de cuotas esto le pasa a mucha gente. Son las mismas reglas que quedan escritas en la promesa."
      >
        <div className="db-reglas">
          {reglas.map((r, i) => (
            <article className="db-regla db-reveal" key={r.titulo} style={retraso(i, 120)}>
              <span className="db-regla-dato db-cifra">{r.dato}</span>
              <h3 className="db-title-2">{r.titulo}</h3>
              <p>{r.cuerpo}</p>
            </article>
          ))}
        </div>

        <p className="db-aviso db-reveal" style={retraso(reglas.length, 120)}>
          Lo que no hacemos: no cobramos gastos de cobranza propios, no publicamos a nadie en
          registros de morosidad por cuotas de una promesa, y no derivamos la cartera a terceros. Si
          te atrasas, la conversación es con nosotros. Para eso está el {empresa.telefono}.
        </p>
      </Section>

      <Faq />

      <Cta
        titulo="¿Te sirve la cuota?"
        bajada="El siguiente paso es ver el terreno. Coordinamos la visita y, si te decides ahí mismo, la evaluación demora dos días hábiles."
      />
    </>
  );
}
