import { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';

import Nav from './Nav';
import Footer from './Footer';
import useInternalLinks from '../hooks/useInternalLinks';

export default function AppDB() {
  const { pathname } = useLocation();
  useInternalLinks();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <>
      <Nav />
      <main id="contenido">
        <Outlet />
      </main>
      <Footer />
    </>
  );
}
