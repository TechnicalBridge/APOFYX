import Hero from '../sections/Hero';
import FeaturedProjects from '../sections/FeaturedProjects';
import Reasons from '../sections/Reasons';
import Steps from '../sections/Steps';
import Stats from '../sections/Stats';
import Testimonials from '../sections/Testimonials';
import Faq from '../sections/Faq';
import Cta from '../sections/Cta';
import useMeta from '../hooks/useMeta';

/*
 * El orden es el recorrido de una decisión de compra: qué vendemos, qué hay
 * disponible, por qué a nosotros, cómo se paga, quiénes somos, a quién le resultó,
 * y las dudas que quedan antes de levantar el teléfono.
 *
 * Los proyectos van segundos, apenas pasado el encabezado. Quien llega a una
 * inmobiliaria viene a ver qué hay, y hacerlo pasar por tres secciones de discurso
 * antes de mostrarle una unidad es la forma más rápida de perderlo.
 */
export default function Home() {
  useMeta({
    titulo: '',
    descripcion:
      'Parcelas, sitios y casas en el Maule y Ñuble con financiamiento directo: cuotas fijas en UF, de 36 a 60 meses, sin crédito hipotecario.',
  });

  return (
    <>
      <Hero />
      <FeaturedProjects />
      <Reasons />
      <Steps />
      <Stats />
      <Testimonials />
      <Faq />
      <Cta />
    </>
  );
}
