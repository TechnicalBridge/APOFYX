import { useId, useMemo, useState } from 'react';

import {
  cotizar,
  enPesos,
  enUF,
  PIE_MINIMO,
  PLAZOS,
  UF_EN_PESOS,
  UF_FECHA,
} from '../domain/financing';
import { getProyectos } from '../services/content';
import type { Proyecto } from '../domain/projects';

/*
 * El cotizador.
 *
 * Es la única pieza interactiva del sitio y hace lo que un comprador hace igual, a
 * mano y peor: dividir el saldo por el número de cuotas. Que esté acá, en el sitio
 * público y sin pedir datos, es una decisión de producto — obligar a dejar el
 * teléfono para conocer la cuota es lo normal en el rubro y es exactamente la
 * fricción que esta empresa dice no tener.
 *
 * Muestra los dos números a la vez, UF y pesos, con la advertencia de cuál manda.
 * Enseñar sólo pesos ocultaría el reajuste; enseñar sólo UF dejaría al comprador
 * sin saber cuánto le sale el mes que viene.
 */

const PIES = [0.2, 0.3, 0.4, 0.5];

interface Props {
  /** En la ficha de un proyecto el precio ya está fijado; en financiamiento, no. */
  proyecto?: Proyecto;
}

export default function Quote({ proyecto }: Props) {
  const proyectos = useMemo(() => getProyectos().filter((p) => p.estado !== 'proximamente'), []);
  const inicial = proyecto ?? proyectos[0]!;

  const [slug, setSlug] = useState(inicial.slug);
  const [pie, setPie] = useState(PIE_MINIMO);
  const [meses, setMeses] = useState(Math.min(60, inicial.plazoMaximo));
  const id = useId();

  const elegido = proyecto ?? proyectos.find((p) => p.slug === slug) ?? inicial;
  // Cambiar de proyecto puede dejar seleccionado un plazo que ese proyecto no
  // ofrece. Se corrige al calcular y no con un efecto que persiga al estado.
  const plazo = Math.min(meses, elegido.plazoMaximo);
  const cuenta = cotizar({ precioUF: elegido.desdeUF, pie, meses: plazo });

  return (
    <div className="db-cotizador">
      <div className="db-cotizador-controles">
        {!proyecto && (
          <div className="db-campo">
            <label htmlFor={`${id}-proyecto`}>Proyecto</label>
            <select
              id={`${id}-proyecto`}
              className="db-select"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
            >
              {proyectos.map((p) => (
                <option key={p.slug} value={p.slug}>
                  {p.nombre} — {p.comuna}
                </option>
              ))}
            </select>
          </div>
        )}

        <fieldset className="db-campo db-opciones">
          <legend>Pie</legend>
          <div className="db-pastillas">
            {PIES.map((v) => (
              <button
                key={v}
                type="button"
                className={`db-pastilla${v === pie ? ' db-pastilla-on' : ''}`}
                aria-pressed={v === pie}
                onClick={() => setPie(v)}
              >
                {Math.round(v * 100)}%
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="db-campo db-opciones">
          <legend>Plazo</legend>
          <div className="db-pastillas">
            {PLAZOS.map((v) => {
              const fuera = v > elegido.plazoMaximo;
              return (
                <button
                  key={v}
                  type="button"
                  className={`db-pastilla${v === plazo ? ' db-pastilla-on' : ''}`}
                  aria-pressed={v === plazo}
                  disabled={fuera}
                  title={
                    fuera
                      ? `${elegido.nombre} se financia hasta ${elegido.plazoMaximo} meses`
                      : undefined
                  }
                  onClick={() => setMeses(v)}
                >
                  {v} meses
                </button>
              );
            })}
          </div>
        </fieldset>
      </div>

      <div className="db-cotizador-salida">
        <p className="db-cotizador-rotulo">Cuota mensual</p>
        <p className="db-cotizador-cuota db-cifra">{enUF(cuenta.cuotaUF)}</p>
        <p className="db-cotizador-pesos db-cifra">≈ {enPesos(cuenta.cuotaEnPesos)} hoy</p>

        <dl className="db-cotizador-detalle">
          <div>
            <dt>Precio desde</dt>
            <dd className="db-cifra">{enUF(elegido.desdeUF)}</dd>
          </div>
          <div>
            <dt>Pie ({Math.round(pie * 100)}%)</dt>
            <dd className="db-cifra">
              {enUF(cuenta.pieUF)}{' '}
              <span className="db-de-total">≈ {enPesos(cuenta.pieEnPesos)}</span>
            </dd>
          </div>
          <div>
            <dt>Saldo en {plazo} cuotas</dt>
            <dd className="db-cifra">{enUF(cuenta.saldoUF)}</dd>
          </div>
        </dl>

        <p className="db-note">
          Cuotas iguales en UF, sin interés. El peso es referencial con la UF de {UF_FECHA} (
          {enPesos(UF_EN_PESOS)}): lo que queda escrito en la promesa es la UF, así que la cuota
          sube con ella. Los gastos operacionales se pagan aparte, con la escritura.
        </p>
      </div>
    </div>
  );
}
