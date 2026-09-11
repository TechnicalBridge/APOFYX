/*
 * Una foto del sitio.
 *
 * Envuelve a `<img>` para tres cosas que en un sitio con muchas imágenes grandes
 * se olvidan de a una y se pagan juntas:
 *
 *   · La caja tiene proporción fija desde antes de que la foto cargue, así el
 *     texto de abajo no salta cuando aparece. Es la diferencia entre una página
 *     que se asienta y una que baila mientras carga.
 *   · Todo lo que no está en el primer pantallazo carga diferido. Una ficha de
 *     proyecto trae cinco fotos y sólo una se ve al entrar.
 *   · El fondo mientras carga es del color de la tierra, no gris: en una
 *     conexión lenta se ve un encuadre cálido y no un hueco.
 *
 * El `alt` es obligatorio en el tipo. Una foto decorativa pasa cadena vacía a
 * propósito, que es distinto de olvidarse.
 */

interface Props {
  /** Nombre del archivo dentro de public/fotos/. */
  archivo: string;
  alt: string;
  /** Ancho/alto de la caja. Por defecto 16/10. */
  proporcion?: string;
  /** La única foto que no se difiere es la del encabezado. */
  prioridad?: boolean;
  /** Encuadre, cuando el motivo no está al centro. */
  posicion?: string;
  /** Para los fondos a sangre: llena la caja del padre en vez de fijar proporción. */
  llenar?: boolean;
  className?: string;
}

export default function Photo({
  archivo,
  alt,
  proporcion = '16 / 10',
  prioridad = false,
  posicion,
  llenar = false,
  className = '',
}: Props) {
  return (
    <span
      className={`db-foto${llenar ? ' db-foto-llena' : ''} ${className}`.trim()}
      style={llenar ? undefined : ({ aspectRatio: proporcion } as React.CSSProperties)}
    >
      <img
        src={`/fotos/${archivo}`}
        alt={alt}
        loading={prioridad ? 'eager' : 'lazy'}
        decoding={prioridad ? 'sync' : 'async'}
        fetchPriority={prioridad ? 'high' : 'auto'}
        style={posicion ? { objectPosition: posicion } : undefined}
      />
    </span>
  );
}
