import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

// El markup de las páginas estáticas viene con <a href="/ruta"> tal cual estaba en
// el sitio original. En vez de reescribir cientos de anclas a <Link>, se atrapa el
// clic acá: los enlaces del propio sitio pasan por el router y el resto sigue su
// camino normal.
export default function useInternalLinks() {
  const navigate = useNavigate();

  useEffect(() => {
    const alHacerClic = (ev: MouseEvent) => {
      if (ev.defaultPrevented || ev.button !== 0) return;
      if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;

      const ancla = (ev.target as Element | null)?.closest?.('a');
      if (!ancla) return;
      if (ancla.target && ancla.target !== '_self') return;
      if (ancla.hasAttribute('download')) return;

      const href = ancla.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:'))
        return;

      const url = new URL(href, window.location.origin);
      if (url.origin !== window.location.origin) return;

      ev.preventDefault();
      // Las rutas de la captura traen barra final ("/blog/"); el router las declara sin ella.
      const ruta = url.pathname.length > 1 ? url.pathname.replace(/\/$/, '') : url.pathname;
      navigate(ruta + url.search + url.hash);
    };

    document.addEventListener('click', alHacerClic);
    return () => document.removeEventListener('click', alHacerClic);
  }, [navigate]);
}
