/*
 * El isotipo de DataBridge: un paño subdividido.
 *
 * La empresa partió tasando suelo y todavía se presenta así, de manera que la marca
 * es un plano de loteo reducido a lo mínimo que sigue leyéndose a 24 píxeles: el
 * deslinde exterior, la línea que parte el paño y un lote pintado. El lote pintado
 * es el que se está comprando.
 */
export function Mark({ tam = 24 }: { tam?: number }) {
  return (
    <svg
      width={tam}
      height={tam}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      {/* el lote que se compra */}
      <path d="M3.25 4.25h7.5v15.5h-7.5z" fill="var(--acento)" />
      {/* el deslinde exterior */}
      <rect
        x="3.25"
        y="4.25"
        width="17.5"
        height="15.5"
        rx="1.25"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      {/* las subdivisiones interiores */}
      <path d="M10.75 4.25v15.5M10.75 12h10" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

interface Props {
  tam?: number;
  /** El footer tiene espacio para decir de qué rubro es; el nav no. */
  conRubro?: boolean;
}

export default function Brand({ tam = 24, conRubro = false }: Props) {
  return (
    <span className={`db-brand${conRubro ? ' db-brand-con-rubro' : ''}`}>
      <Mark tam={tam} />
      <span className="db-brand-nombres">
        <span className="db-brand-text">
          Data<span className="db-brand-accent">Bridge</span>
        </span>
        {conRubro && <span className="db-brand-rubro">Inmobiliaria</span>}
      </span>
    </span>
  );
}
