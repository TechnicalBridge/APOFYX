import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import PageHead from '../ui/PageHead';
import { revisar, enviarConsulta, type Consulta } from '../services/contact';
import { getEmpresa, getProyectos } from '../services/content';
import useMeta from '../hooks/useMeta';

/*
 * La consulta por un proyecto.
 *
 * Pide cuatro cosas y ninguna de más. Este formulario existe para coordinar una
 * visita, no para levantar un perfil: preguntar renta, rubro o «cuándo piensas
 * comprar» antes de haber mostrado el terreno es exactamente la fricción que la
 * empresa dice no tener, y el cotizador ya funciona sin pedir nada.
 *
 * El proyecto viene preseleccionado por query string cuando se llega desde una
 * ficha, así nadie tiene que volver a elegir lo que estaba mirando.
 */

const vacia = (proyecto: string): Consulta => ({
  nombre: '',
  email: '',
  telefono: '',
  proyecto,
  mensaje: '',
});

export default function Contact() {
  useMeta({
    titulo: 'Contacto',
    descripcion:
      'Coordina una visita a cualquiera de nuestros proyectos, sin compromiso y sin reservar nada. Talca, Región del Maule.',
  });

  const [params] = useSearchParams();
  const empresa = getEmpresa();
  const proyectos = getProyectos();

  const [datos, setDatos] = useState<Consulta>(() => vacia(params.get('proyecto') ?? ''));
  const [fallos, setFallos] = useState<Partial<Record<keyof Consulta, string>>>({});
  const [enviando, setEnviando] = useState(false);
  const [listo, setListo] = useState(false);
  const [error, setError] = useState('');

  const cambiar =
    (campo: keyof Consulta) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      setDatos((d) => ({ ...d, [campo]: e.target.value }));
      // El error se limpia al corregir, no al reenviar: castigar dos veces por el
      // mismo dato es la forma más rápida de que alguien abandone un formulario.
      if (fallos[campo]) setFallos((f) => ({ ...f, [campo]: undefined }));
    };

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    const problemas = revisar(datos);
    setFallos(problemas);
    if (Object.keys(problemas).length > 0) {
      document.getElementById(Object.keys(problemas)[0]!)?.focus();
      return;
    }

    setEnviando(true);
    setError('');
    const r = await enviarConsulta(datos);
    setEnviando(false);
    if (r.estado === 'enviado') setListo(true);
    else setError(r.motivo);
  };

  const campo = (
    nombre: keyof Consulta,
    etiqueta: string,
    extra?: { tipo?: string; ayuda?: string; area?: boolean },
  ) => (
    <div className={`db-campo${fallos[nombre] ? ' db-campo-mal' : ''}`}>
      <label htmlFor={nombre}>{etiqueta}</label>
      {extra?.area ? (
        <textarea
          id={nombre}
          className="db-textarea"
          rows={4}
          value={datos[nombre] ?? ''}
          onChange={cambiar(nombre)}
        />
      ) : (
        <input
          id={nombre}
          className="db-input"
          type={extra?.tipo ?? 'text'}
          value={datos[nombre] ?? ''}
          onChange={cambiar(nombre)}
          aria-invalid={Boolean(fallos[nombre])}
          aria-describedby={fallos[nombre] ? `${nombre}-error` : undefined}
        />
      )}
      {extra?.ayuda && !fallos[nombre] && <p className="db-note">{extra.ayuda}</p>}
      {fallos[nombre] && (
        <p className="db-error" id={`${nombre}-error`}>
          {fallos[nombre]}
        </p>
      )}
    </div>
  );

  return (
    <>
      <PageHead
        rotulo="Contacto"
        titulo="Coordinemos una visita."
        bajada="Se puede ir a ver el terreno sin haber reservado nada y sin compromiso. Te respondemos el mismo día hábil."
      />

      <section className="db-section">
        <div className="db-container db-contacto">
          {listo ? (
            <div className="db-exito" role="status">
              <span className="db-badge db-badge-ok">Consulta enviada</span>
              <p>
                Gracias, {datos.nombre.split(' ')[0]}. Te escribimos a{' '}
                <strong>{datos.email}</strong> o te llamamos al{' '}
                <strong className="db-cifra">{datos.telefono}</strong> para coordinar la visita.
              </p>
              <p className="db-note">
                Este sitio es un proyecto de capstone: la consulta no llega a ningún buzón real.
              </p>
            </div>
          ) : (
            <form className="db-form" onSubmit={enviar} noValidate>
              {campo('nombre', 'Tu nombre')}
              {campo('email', 'Correo', { tipo: 'email' })}
              {campo('telefono', 'Teléfono', {
                tipo: 'tel',
                ayuda: 'Es por donde más rápido respondemos.',
              })}

              <div className="db-campo">
                <label htmlFor="proyecto">Proyecto que te interesa</label>
                <select
                  id="proyecto"
                  className="db-select"
                  value={datos.proyecto}
                  onChange={cambiar('proyecto')}
                >
                  <option value="">Todavía no lo tengo claro</option>
                  {proyectos.map((p) => (
                    <option key={p.slug} value={p.slug}>
                      {p.nombre} — {p.comuna}
                    </option>
                  ))}
                </select>
              </div>

              {campo('mensaje', 'Algo que quieras contarnos (opcional)', { area: true })}

              {error && (
                <p className="db-error" role="alert">
                  {error}
                </p>
              )}

              <button className="db-btn db-btn-primary" type="submit" disabled={enviando}>
                {enviando ? 'Enviando…' : 'Enviar consulta'}
              </button>
            </form>
          )}

          <aside className="db-prosa db-contacto-lado">
            <h2>Qué pasa después</h2>
            <p>
              Te llamamos para acordar día y hora. La visita la hace alguien de la empresa, no un
              corredor externo, y se va con el plano de loteo impreso para mirarlo en terreno.
            </p>

            <h2>Si prefieres ir directo</h2>
            <p>
              {empresa.direccion}, {empresa.comuna}.
              <br />
              <span className="db-note">{empresa.horario}</span>
            </p>

            <h2>O escríbenos</h2>
            <p>
              <a href={`mailto:${empresa.correoVentas}`}>{empresa.correoVentas}</a>
              <br />
              <a className="db-cifra" href={`tel:${empresa.telefono.replace(/\s/g, '')}`}>
                {empresa.telefono}
              </a>
            </p>
          </aside>
        </div>
      </section>
    </>
  );
}
