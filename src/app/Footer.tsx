import { Link } from 'react-router-dom';

import Brand from '../ui/Brand';
import { getEmpresa, getDisponibles } from '../services/content';

/*
 * El pie.
 *
 * La columna de proyectos se arma sola con los que están en venta. Antes era una
 * lista escrita a mano, que es como un pie de página termina enlazando durante un
 * año a un proyecto que se agotó en marzo.
 */
export default function Footer() {
  const empresa = getEmpresa();
  const proyectos = getDisponibles();

  return (
    <footer className="db-pie">
      <div className="db-container db-footer-row">
        <div className="db-footer-brand">
          <Brand conRubro />
          <address className="db-footer-dir">
            {empresa.direccion}
            <br />
            {empresa.comuna}
          </address>
          <a
            className="db-footer-fono db-cifra"
            href={`tel:${empresa.telefono.replace(/\s/g, '')}`}
          >
            {empresa.telefono}
          </a>
          <a className="db-footer-mail" href={`mailto:${empresa.correoVentas}`}>
            {empresa.correoVentas}
          </a>
        </div>

        <nav className="db-footer-col" aria-label="Proyectos">
          <p className="db-footer-col-title">Proyectos</p>
          {proyectos.map((p) => (
            <Link key={p.slug} to={`/proyectos/${p.slug}`}>
              {p.nombre}
            </Link>
          ))}
          <Link to="/proyectos">Ver todos</Link>
        </nav>

        <nav className="db-footer-col" aria-label="Empresa">
          <p className="db-footer-col-title">Empresa</p>
          <Link to="/nosotros">Nosotros</Link>
          <Link to="/financiamiento">Financiamiento</Link>
          <Link to="/contacto">Contacto</Link>
        </nav>

        <nav className="db-footer-col" aria-label="Legal">
          <p className="db-footer-col-title">Legal</p>
          <Link to="/terminos">Términos</Link>
          <Link to="/privacidad">Privacidad</Link>
          <Link to="/creditos">Créditos fotográficos</Link>
        </nav>
      </div>

      <div className="db-container db-footer-base">
        <span className="db-note">© 2026 {empresa.nombre}</span>
        {/* El sitio es material de un trabajo académico y conviene que lo diga
            en cada página, no sólo en la letra chica de los términos. */}
        <span className="db-note">
          Proyecto de capstone · empresa, proyectos y precios ficticios
        </span>
      </div>
    </footer>
  );
}
