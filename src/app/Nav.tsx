import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import Brand from '../ui/Brand';
import { getEmpresa, getProyectos } from '../services/content';
import { enUF } from '../domain/financing';

const ENLACES: [string, string][] = [
  ['Proyectos', '/proyectos'],
  ['Financiamiento', '/financiamiento'],
  ['Nosotros', '/nosotros'],
];

export default function Nav() {
  const [abierto, setAbierto] = useState(false);
  const [conScroll, setConScroll] = useState(false);
  const { pathname } = useLocation();
  const empresa = getEmpresa();
  const desde = Math.min(...getProyectos().map((p) => p.desdeUF));

  useEffect(() => {
    const alScrollear = () => setConScroll(window.scrollY > 24);
    alScrollear();
    window.addEventListener('scroll', alScrollear, { passive: true });
    return () => window.removeEventListener('scroll', alScrollear);
  }, []);

  // El menú abierto bloquea el fondo; si no, el scroll se lo lleva por detrás.
  useEffect(() => {
    document.body.style.overflow = abierto ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [abierto]);

  useEffect(() => {
    const alTeclear = (ev: KeyboardEvent) => ev.key === 'Escape' && setAbierto(false);
    document.addEventListener('keydown', alTeclear);
    return () => document.removeEventListener('keydown', alTeclear);
  }, []);

  // Navegar con el menú abierto lo dejaría flotando sobre la página nueva.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setAbierto(false), [pathname]);

  // Una ficha de proyecto tiene que marcar «Proyectos» en el menú, y /proyectos
  // no debe encenderse desde /proyectos-algo-más: de ahí la barra.
  const activo = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <header className={`db-nav${conScroll ? ' db-nav-stuck' : ''}`}>
      <a className="db-saltar" href="#contenido">
        Saltar al contenido
      </a>

      {/* Los cuatro datos que deciden si alguien sigue leyendo. En este rubro van
          arriba de todo porque son la objeción y la respuesta a la vez: no hay
          banco, la cuota no se mueve y hay algo barato de dónde partir. */}
      <p className="db-barra-datos">
        <span>Financiamiento directo, sin bancos</span>
        <span aria-hidden="true">·</span>
        <span>Cuotas fijas en UF</span>
        <span aria-hidden="true">·</span>
        <span className="db-cifra">Desde {enUF(desde)}</span>
        <span aria-hidden="true">·</span>
        <span>Maule y Ñuble</span>
      </p>

      <div className="db-nav-row db-container">
        <Link className="db-nav-brand" to="/" aria-label={`${empresa.nombre}, inicio`}>
          <Brand />
        </Link>

        <nav className="db-nav-links" aria-label="Principal">
          {ENLACES.map(([rotulo, href]) => (
            <Link
              key={href}
              to={href}
              className={`db-nav-link${activo(href) ? ' db-nav-current' : ''}`}
              aria-current={activo(href) ? 'page' : undefined}
            >
              {rotulo}
            </Link>
          ))}
        </nav>

        <div className="db-nav-actions">
          <a className="db-nav-fono db-cifra" href={`tel:${empresa.telefono.replace(/\s/g, '')}`}>
            {empresa.telefono}
          </a>
          <Link className="db-btn db-btn-primary db-nav-cta" to="/contacto">
            Coordinar visita
          </Link>
          <button
            type="button"
            className="db-nav-menu"
            aria-expanded={abierto}
            aria-controls="db-menu"
            aria-label={abierto ? 'Cerrar menú' : 'Abrir menú'}
            onClick={() => setAbierto((v) => !v)}
          >
            <span />
            <span />
          </button>
        </div>
      </div>

      <div className="db-panel" id="db-menu" hidden={!abierto}>
        <div className="db-container db-panel-list">
          {ENLACES.map(([rotulo, href]) => (
            <Link key={href} to={href} className="db-panel-link">
              {rotulo}
            </Link>
          ))}
          <Link className="db-btn db-btn-primary" to="/contacto">
            Coordinar visita
          </Link>
          <a className="db-panel-fono db-cifra" href={`tel:${empresa.telefono.replace(/\s/g, '')}`}>
            {empresa.telefono}
          </a>
        </div>
      </div>
    </header>
  );
}
