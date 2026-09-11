import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';

import App from './App';
import Home from '../pages/Home';
import Projects from '../pages/Projects';
import Project from '../pages/Project';
import Financing from '../pages/Financing';
import About from '../pages/About';
import Contact from '../pages/Contact';
import Legal from '../pages/Legal';
import Credits from '../pages/Credits';
import NotFound from '../pages/NotFound';

import '../styles/base.css';
import '../styles/components.css';
import '../styles/sections.css';
import '../styles/pages.css';

// El contenedor lo escribe index.html; si falta, el fallo tiene que ser ruidoso y
// no un render silencioso a ninguna parte.
const raiz = document.getElementById('app');
if (!raiz) throw new Error('Falta el contenedor #app en index.html');

createRoot(raiz).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<Home />} />
          <Route path="proyectos" element={<Projects />} />
          <Route path="proyectos/:slug" element={<Project />} />
          <Route path="financiamiento" element={<Financing />} />
          <Route path="nosotros" element={<About />} />
          <Route path="contacto" element={<Contact />} />
          <Route path="creditos" element={<Credits />} />
          <Route path="terminos" element={<Legal documento="terminos" />} />
          <Route path="privacidad" element={<Legal documento="privacidad" />} />
          {/* Una dirección desconocida dice qué pasó en vez de dibujar la portada:
              alguien que llega a /proyectos/altos-de-panguilemú con tilde merece
              saber que erró la dirección, no quedarse pensando que el proyecto ya
              no existe. */}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
