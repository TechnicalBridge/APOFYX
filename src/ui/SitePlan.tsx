import type { Proyecto } from '../domain/projects';
import { trazarEdificio, trazarLoteo, type Caja, type Lote } from './plan-layout';

/*
 * El plano técnico del proyecto, sin terreno.
 *
 * Es la contraparte de `TerrainView`: la vista aérea muestra cómo se ve el paño y
 * esto muestra cómo está subdividido. Van juntas en la ficha porque responden
 * preguntas distintas —«¿me gusta el lugar?» y «¿cuál lote me toca?»— y porque una
 * imagen bonita sin plano es exactamente lo que hace desconfiar de este rubro.
 *
 * Los lotes pintados son los vendidos y los vacíos los que quedan, de manera que
 * «quedan 17 de 48» se ve además de leerse. Cuando el backend sirva la
 * disponibilidad real, el dibujo se actualiza solo.
 *
 * La geometría sale de `plan-layout.ts`, compartida con la vista aérea: las dos
 * tienen que mostrar la misma subdivisión.
 */

const CAJA: Caja = { ancho: 400, alto: 250, margen: 16 };

/** Una casa dentro del sitio: cuerpo y techo a dos aguas. */
function casita(l: Lote) {
  const ancho = Math.min(l.w * 0.62, l.h * 0.62);
  const cx = l.x + l.w / 2;
  const cy = l.y + l.h / 2;
  const mitad = ancho / 2;
  const cuerpo = ancho * 0.58;
  const techo = ancho * 0.42;
  const base = cy + ancho * 0.4;

  return `M${cx - mitad} ${base} v${-cuerpo} l${mitad} ${-techo} l${mitad} ${techo} v${cuerpo} z`;
}

interface Props {
  proyecto: Proyecto;
  /** En las tarjetas el plano es decorativo; en la ficha, informativo. */
  compacto?: boolean;
}

export default function SitePlan({ proyecto, compacto = false }: Props) {
  const esEdificio = proyecto.tipo === 'departamentos';
  const lotes = esEdificio ? trazarEdificio(proyecto, CAJA) : trazarLoteo(proyecto, CAJA).lotes;
  const conCasas = proyecto.tipo === 'casas';
  const unidad = esEdificio ? 'departamentos' : conCasas ? 'casas' : 'sitios';

  return (
    <svg
      className={`db-plano${compacto ? ' db-plano-compacto' : ''}`}
      viewBox={`0 0 ${CAJA.ancho} ${CAJA.alto}`}
      role="img"
      aria-label={`Plano de ${proyecto.nombre}: ${proyecto.unidades} ${unidad}, ${proyecto.disponibles} disponibles.`}
      preserveAspectRatio="xMidYMid meet"
    >
      <rect width={CAJA.ancho} height={CAJA.alto} fill="var(--plano-fondo)" />

      {/* La trama de fondo hace de cuadrícula del papel. */}
      <defs>
        <pattern id={`trama-${proyecto.slug}`} width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M20 0H0V20" fill="none" stroke="var(--plano-trama)" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width={CAJA.ancho} height={CAJA.alto} fill={`url(#trama-${proyecto.slug})`} />

      {esEdificio && (
        <line
          x1={CAJA.margen - 6}
          y1={CAJA.alto - CAJA.margen - 10}
          x2={CAJA.ancho - CAJA.margen + 6}
          y2={CAJA.alto - CAJA.margen - 10}
          stroke="var(--plano-linea)"
          strokeWidth="1.5"
        />
      )}

      {lotes.map((l, i) => (
        <g key={i}>
          <rect
            x={l.x}
            y={l.y}
            width={Math.max(l.w, 0)}
            height={Math.max(l.h, 0)}
            rx={esEdificio ? 1 : 1.5}
            fill={l.vendido && !conCasas ? 'var(--plano-lleno)' : 'var(--plano-vacio)'}
            stroke="var(--plano-linea)"
            strokeWidth="0.9"
          />
          {conCasas && l.vendido && <path d={casita(l)} fill="var(--plano-lleno-fuerte)" />}
        </g>
      ))}

      {/* Norte: convención de plano, y de paso ancla la lectura del dibujo. */}
      {!esEdificio && (
        <g transform={`translate(${CAJA.ancho - 26} ${CAJA.alto - 16})`} aria-hidden="true">
          <path
            d="M0 0 V-16 M0 -16 l-3.5 5 M0 -16 l3.5 5"
            stroke="var(--plano-norte)"
            strokeWidth="1.2"
            fill="none"
          />
          <text x="0" y="8" textAnchor="middle" fill="var(--plano-norte)" fontSize="9">
            N
          </text>
        </g>
      )}
    </svg>
  );
}
