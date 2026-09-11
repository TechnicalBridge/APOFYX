import PageHead from '../ui/PageHead';
import { getEmpresa } from '../services/content';
import useMeta from '../hooks/useMeta';

/*
 * Términos y privacidad en una sola pieza: son dos textos cortos con la misma
 * forma, y separarlos en dos archivos sería duplicar el andamiaje por nada.
 *
 * Están escritos para lo que este sitio realmente es —un trabajo académico sobre
 * una inmobiliaria que no existe— en vez de copiar el contrato de una empresa real.
 * Eso importa más que de costumbre acá: un sitio que muestra precios, plazos y una
 * política de mora se parece lo suficiente a una oferta como para que convenga
 * decir, en letra grande, que no lo es.
 */

interface Props {
  documento: 'terminos' | 'privacidad';
}

export default function Legal({ documento }: Props) {
  const empresa = getEmpresa();
  const esPrivacidad = documento === 'privacidad';

  useMeta({
    titulo: esPrivacidad ? 'Privacidad' : 'Términos',
    descripcion: esPrivacidad
      ? 'Qué datos recoge este sitio y qué se hace con ellos. Sin analítica ni cookies de seguimiento.'
      : 'Condiciones de uso del sitio. Nada de lo publicado constituye una oferta: es un proyecto académico con una empresa ficticia.',
  });

  return (
    <>
      <PageHead
        rotulo={esPrivacidad ? 'Privacidad' : 'Términos'}
        titulo={esPrivacidad ? 'Qué hacemos con tus datos' : 'Condiciones de uso'}
        bajada="Última actualización: septiembre de 2026."
      />

      <section className="db-section">
        <div className="db-container db-prosa">
          <h2>Qué es este sitio</h2>
          <p>
            {empresa.nombre} es un proyecto académico de capstone. No es una empresa constituida, no
            vende inmuebles y no tiene compradores. Los proyectos, las comunas donde dice tener
            paños, los precios, las cifras y las personas citadas son ficticios y fueron creados
            para ilustrar el sitio de una inmobiliaria.
          </p>
          <p>
            Cualquier parecido con una empresa real es casualidad: los nombres fueron inventados
            para este trabajo.
          </p>

          {esPrivacidad ? (
            <>
              <h2>Qué datos se recogen</h2>
              <p>
                Sólo lo que escribas en el formulario de contacto: nombre, correo, teléfono, el
                proyecto que te interesa y el mensaje. No hay analítica, no hay cookies de
                seguimiento y no hay terceros mirando tu visita.
              </p>

              <h2>Qué se hace con ellos</h2>
              <p>
                En la versión actual, nada: el formulario no envía la información a ningún servidor
                y la consulta no llega a ningún buzón. El cotizador calcula en tu propio navegador y
                no registra lo que pruebas.
              </p>

              <h2>No subas datos de personas reales</h2>
              <p>
                Este sitio es material de demostración. No cargues en él información de compradores,
                deudores ni de ninguna persona identificable, ni siquiera a modo de prueba.
              </p>

              <h2>Tus derechos</h2>
              <p>
                Puedes pedir que se elimine cualquier dato que nos hayas enviado escribiendo a{' '}
                <a href={`mailto:${empresa.correo}`}>{empresa.correo}</a>.
              </p>
            </>
          ) : (
            <>
              <h2>Esto no es una oferta</h2>
              <p>
                Nada de lo que se lee acá constituye una oferta comercial, una promesa de venta ni
                asesoría legal o financiera. Los precios en UF, los plazos, las unidades disponibles
                y la política de mora son material ilustrativo de un trabajo universitario y no
                corresponden a ningún inmueble existente.
              </p>

              <h2>Las fotografías</h2>
              <p>
                Las imágenes son de terceros, están bajo licencias Creative Commons e ilustran
                proyectos inventados: no corresponden a los terrenos ni a las comunas que el sitio
                menciona. La autoría y la licencia de cada una están en{' '}
                <a href="/creditos">créditos fotográficos</a>.
              </p>

              <h2>El cotizador</h2>
              <p>
                Calcula dividiendo el saldo en cuotas iguales en UF, sin interés, con un valor de UF
                fijo escrito en el código. Sirve para mostrar cómo funcionaría el cálculo: no es una
                cotización, no reserva nada y no considera gastos operacionales.
              </p>

              <h2>Uso del sitio</h2>
              <p>
                Puedes navegarlo, leerlo y mostrarlo libremente. El código y los textos son obra de
                sus autores en el marco de un trabajo universitario; si quieres reutilizar algo,
                escríbenos a <a href={`mailto:${empresa.correo}`}>{empresa.correo}</a>.
              </p>

              <h2>Cambios</h2>
              <p>
                El proyecto está en desarrollo y estas condiciones pueden cambiar mientras avanza.
              </p>
            </>
          )}
        </div>
      </section>
    </>
  );
}
