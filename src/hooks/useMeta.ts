import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

import { EMPRESA } from '../domain/company';

/*
 * Título, descripción y tarjeta de enlace por ruta.
 *
 * POR QUÉ IMPORTA ACÁ MÁS QUE EN OTROS SITIOS
 * Una ficha de proyecto es exactamente lo que la gente copia y manda por WhatsApp.
 * Si todas las URL comparten el mismo <title> y la misma descripción, ese mensaje
 * llega diciendo «DataBridge Inmobiliaria» en vez de «Altos de Panguilemu — 48
 * parcelas de 5.000 m² en San Clemente», y el enlace deja de vender solo.
 *
 * Escribe en el <head> con efectos en vez de usar una librería: son cuatro etiquetas
 * y una dependencia menos. El prerender captura el head ya escrito, así que el HTML
 * de cada ruta sale a disco con su propio título.
 */

const SITIO = `${EMPRESA.nombre} ${EMPRESA.rubro}`;

/** Crea la etiqueta la primera vez y la reusa después, en vez de acumular copias. */
function fijarMeta(clave: 'name' | 'property', valor: string, contenido: string) {
  const selector = `meta[${clave}="${valor}"]`;
  let nodo = document.head.querySelector<HTMLMetaElement>(selector);
  if (!nodo) {
    nodo = document.createElement('meta');
    nodo.setAttribute(clave, valor);
    document.head.appendChild(nodo);
  }
  nodo.setAttribute('content', contenido);
}

function fijarCanonica(url: string) {
  let nodo = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!nodo) {
    nodo = document.createElement('link');
    nodo.rel = 'canonical';
    document.head.appendChild(nodo);
  }
  nodo.href = url;
}

interface Meta {
  /** Sin el nombre de la empresa: se agrega acá. La portada pasa cadena vacía. */
  titulo: string;
  descripcion: string;
}

export default function useMeta({ titulo, descripcion }: Meta) {
  const { pathname } = useLocation();

  useEffect(() => {
    const completo = titulo ? `${titulo} · ${SITIO}` : `${SITIO} — ${EMPRESA.promesa}`;
    document.title = completo;

    fijarMeta('name', 'description', descripcion);
    fijarMeta('property', 'og:title', completo);
    fijarMeta('property', 'og:description', descripcion);
    fijarMeta('property', 'og:type', 'website');
    fijarMeta('property', 'og:site_name', SITIO);

    // Sin dominio propio todavía, la canónica se arma con el origen que sirva la
    // página. Es lo correcto igual: evita que /proyectos/x y /proyectos/x?utm=…
    // cuenten como dos páginas distintas.
    if (typeof window !== 'undefined') {
      const url = `${window.location.origin}${pathname}`;
      fijarCanonica(url);
      fijarMeta('property', 'og:url', url);
    }
  }, [titulo, descripcion, pathname]);
}
