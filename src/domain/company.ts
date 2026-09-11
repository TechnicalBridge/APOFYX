/*
 * DataBridge — la empresa.
 *
 * QUÉ ES ESTE SITIO
 * DataBridge es una inmobiliaria ficticia: desarrolla loteos y proyectos
 * habitacionales en el Maule y Ñuble, y los vende con financiamiento directo —
 * sin banco, en cuotas fijas en UF. Esto es el sitio público de esa empresa: lo
 * que ve alguien que está pensando en comprar.
 *
 * POR QUÉ IMPORTA EL FINANCIAMIENTO DIRECTO
 * Es lo que la hace acreedora. Una inmobiliaria que vende con crédito hipotecario
 * cobra una vez y el banco se queda con la deuda; una que financia directo se
 * queda con una cartera propia de compradores pagando mes a mes durante cinco
 * años. Toda la identidad de la empresa sale de ahí, y por eso el sitio le dedica
 * una página entera a explicar cómo se paga y qué pasa cuando alguien se atrasa.
 *
 * TODO ES INVENTADO
 * La empresa, los proyectos, las comunas donde dice tener paños, las cifras y las
 * personas que aparecen citadas son material de demostración para un capstone. No
 * corresponden a ninguna compañía real, a ningún loteo real ni a ninguna persona
 * real, y nada de lo que se lee acá es una oferta.
 */

export interface Empresa {
  nombre: string;
  rubro: string;
  promesa: string;
  bajada: string;
  origen: string;
  correo: string;
  correoVentas: string;
  telefono: string;
  direccion: string;
  comuna: string;
  horario: string;
}

export const EMPRESA: Empresa = {
  nombre: 'DataBridge',
  rubro: 'Inmobiliaria',
  promesa: 'Tu terreno sin pasar por el banco.',
  bajada:
    'Financiamos directo: cuotas fijas en UF, entre 36 y 60 meses, sin crédito hipotecario. El plazo te lo damos nosotros, así que también somos nosotros los que respondemos cuando algo se complica.',
  origen:
    'Partimos en 2014 tasando suelo para otros. El nombre quedó de esa época y el método también: todavía elegimos los paños mirando datos antes que vistas.',
  correo: 'contacto@databridge.cl',
  correoVentas: 'ventas@databridge.cl',
  telefono: '+56 71 234 5678',
  direccion: '2 Norte 1340, oficina 503',
  comuna: 'Talca, Región del Maule',
  horario: 'Lunes a viernes, 9:00 a 18:30 · Sábados, 10:00 a 14:00',
};

// --- por qué comprarnos a nosotros -------------------------------------------

export interface Razon {
  clave: 'suelo' | 'financiamiento' | 'escritura';
  titulo: string;
  bajada: string;
  cuerpo: string;
}

export const RAZONES: Razon[] = [
  {
    clave: 'suelo',
    titulo: 'El paño se elige con datos',
    bajada: 'Lo que no aparece en las fotos.',
    cuerpo:
      'Antes de comprar un terreno revisamos rol, uso de suelo, derechos de agua inscritos, factibilidad eléctrica y cómo se llega en julio, no en enero. De cada diez paños que evaluamos compramos tres. Los otros siete tenían algo que no resistía la revisión.',
  },
  {
    clave: 'financiamiento',
    titulo: 'Financiamos nosotros',
    bajada: 'Sin banco y sin hipotecario.',
    cuerpo:
      'La cuota es fija en UF, de 36 a 60 meses, y la evaluación mira capacidad de pago real —no el puntaje en un registro de morosidad. Buena parte de nuestros compradores son independientes con ingresos que un banco no sabe leer.',
  },
  {
    clave: 'escritura',
    titulo: 'La escritura no es una sorpresa',
    bajada: 'La fecha está desde el día uno.',
    cuerpo:
      'Lo que se firma al principio es una promesa de compraventa ante notario con la fecha de escritura escrita adentro, junto con los gastos operacionales calculados. No hay cobros que aparecen al final ni plazos que se corren.',
  },
];

// --- cómo se compra ----------------------------------------------------------

export interface Paso {
  n: string;
  titulo: string;
  cuerpo: string;
  plazo: string;
}

export const PASOS: Paso[] = [
  {
    n: '01',
    titulo: 'Reserva',
    cuerpo:
      'Se elige la unidad y se paga una reserva de 10 UF que la saca de la venta por quince días. Si la evaluación no resulta, la reserva se devuelve completa; si resulta, se descuenta del pie.',
    plazo: 'Mismo día',
  },
  {
    n: '02',
    titulo: 'Evaluación',
    cuerpo:
      'Pedimos tres meses de ingreso —liquidaciones, boletas o cartola, según cómo trabajes— y calculamos hasta qué cuota llegas sin ahogarte. Si el número no da, proponemos un plazo más largo antes que un monto más chico.',
    plazo: '2 días hábiles',
  },
  {
    n: '03',
    titulo: 'Promesa y pie',
    cuerpo:
      'Se firma la promesa de compraventa ante notario. Trae el precio en UF, el número de cuotas, la fecha de escritura y los gastos operacionales. El pie es el 20% y también se puede pagar en cuotas.',
    plazo: 'Dentro de los 15 días',
  },
  {
    n: '04',
    titulo: 'Cuotas y escritura',
    cuerpo:
      'La cuota vence los 5 de cada mes. Al pagar la última se firma la escritura y el terreno se inscribe a tu nombre en el Conservador de Bienes Raíces. Ese trámite lo hacemos nosotros.',
    plazo: 'De 36 a 60 meses',
  },
];

/*
 * Las reglas de la cartera.
 *
 * Esto es lo que hace que DataBridge sea un acreedor y no sólo un vendedor: una
 * política de mora escrita, con plazos concretos. Va en el sitio público a
 * propósito —un comprador que financia a cinco años tiene derecho a saber qué pasa
 * el mes que no puede pagar antes de firmar, no después.
 */
export interface Regla {
  titulo: string;
  cuerpo: string;
  dato: string;
}

export const REGLAS: Regla[] = [
  {
    titulo: 'Diez días de gracia',
    cuerpo:
      'La cuota vence el 5 y hasta el 15 se paga igual, sin recargo ni llamado. Un atraso de una semana le pasa a cualquiera y no tiene por qué costar plata.',
    dato: 'Día 15',
  },
  {
    titulo: 'Después corre interés corriente',
    cuerpo:
      'Desde el día 16 se aplica el interés corriente para operaciones no reajustables que fija la Comisión para el Mercado Financiero. Ni un peso por sobre eso: no cobramos gastos de cobranza propios.',
    dato: 'Día 16',
  },
  {
    titulo: 'A los 90 días, repactación primero',
    cuerpo:
      'Tres cuotas impagas abren un incumplimiento, pero antes de cualquier otra cosa se ofrece repactar. Recién si no hay acuerdo se aplica lo que dice la promesa.',
    dato: 'Día 90',
  },
  {
    titulo: 'Una repactación por contrato',
    cuerpo:
      'Se juntan las cuotas atrasadas y se reparten en hasta 12 cuotas nuevas, sin cambiar el precio en UF. Se puede hacer una vez por contrato y no requiere volver a evaluar.',
    dato: 'Hasta 12 cuotas',
  },
];

// --- la empresa por dentro ---------------------------------------------------

export interface Cifra {
  /** Numérico para que el contador pueda animarlo. */
  valor: number;
  sufijo?: string;
  etiqueta: string;
  detalle: string;
}

export const CIFRAS: Cifra[] = [
  {
    valor: 12,
    etiqueta: 'años eligiendo suelo',
    detalle: 'los tres primeros, tasando para otros',
  },
  {
    valor: 9,
    etiqueta: 'proyectos desarrollados',
    detalle: 'seis loteos, dos condominios y un edificio',
  },
  {
    valor: 870,
    etiqueta: 'escrituras firmadas',
    detalle: 'inscritas en el Conservador por nosotros',
  },
  {
    valor: 612,
    etiqueta: 'compradores pagando hoy',
    detalle: 'cartera propia, sin banco de por medio',
  },
];

export interface Hito {
  ano: string;
  titulo: string;
  cuerpo: string;
}

export const HITOS: Hito[] = [
  {
    ano: '2014',
    titulo: 'Una oficina de tasación',
    cuerpo:
      'Tres personas en 2 Norte cruzando roles, uso de suelo y accesos para clientes que querían comprar paños en el secano. No desarrollábamos nada: sólo decíamos dónde no comprar.',
  },
  {
    ano: '2017',
    titulo: 'El primer loteo propio',
    cuerpo:
      'Después de tres años recomendando terrenos ajenos compramos 18 hectáreas en Linares y las loteamos nosotros. Salió Vega Alegre, que hoy va en su tercera etapa.',
  },
  {
    ano: '2019',
    titulo: 'Empezamos a financiar',
    cuerpo:
      'El banco rechazaba a casi la mitad de nuestros compradores por tener ingresos informales, no por no poder pagar. En vez de bajar el precio empezamos a dar el crédito nosotros.',
  },
  {
    ano: '2022',
    titulo: 'Del sitio al departamento',
    cuerpo:
      'Mirador del Maule fue el primer edificio: 64 departamentos a cuatro cuadras de la Plaza de Armas de Talca. Mismo esquema de financiamiento, otra escala de obra.',
  },
  {
    ano: '2026',
    titulo: 'Cuatro comunas',
    cuerpo:
      'Hoy vendemos en San Clemente, Linares, Cauquenes y Chillán, con una cartera propia de 612 compradores al día en sus cuotas.',
  },
];

// --- lo que dicen los compradores --------------------------------------------

export interface Testimonio {
  persona: string;
  lugar: string;
  proyecto: string;
  cita: string;
}

export const TESTIMONIOS: Testimonio[] = [
  {
    persona: 'Marcela y Rodrigo O.',
    lugar: 'Talca',
    proyecto: 'Altos de Panguilemu',
    cita: 'Los dos trabajamos por boleta y en dos bancos nos dijeron que no sin mirarnos la cartola. Acá la miraron, nos bajaron la cuota estirando el plazo y firmamos el mismo mes.',
  },
  {
    persona: 'Héctor P.',
    lugar: 'Linares',
    proyecto: 'Vega Alegre III',
    cita: 'Me atrasé cuatro meses cuando cerró el taller. Llamé yo antes de que me llamaran y me repactaron sin discutir. Terminé de pagar el año pasado.',
  },
  {
    persona: 'Familia Sanhueza',
    lugar: 'Chillán',
    proyecto: 'Barrio Los Robles',
    cita: 'Lo que más pesó fue que la fecha de escritura estaba escrita en la promesa. En los otros proyectos que vimos nadie nos la quiso poner por escrito.',
  },
];

// --- preguntas ---------------------------------------------------------------

export interface Pregunta {
  pregunta: string;
  respuesta: string;
}

export const PREGUNTAS: Pregunta[] = [
  {
    pregunta: '¿Necesito crédito hipotecario?',
    respuesta:
      'No. El financiamiento es directo con nosotros: firmas una promesa de compraventa y pagas cuotas mensuales. No interviene ningún banco y no se constituye hipoteca.',
  },
  {
    pregunta: '¿Me evalúan por Dicom?',
    respuesta:
      'No usamos el registro de morosidad como filtro. Pedimos tres meses de ingresos —liquidaciones, boletas o cartola— para calcular hasta qué cuota puedes llegar. Estar publicado no te deja fuera.',
  },
  {
    pregunta: '¿Cuándo queda el terreno a mi nombre?',
    respuesta:
      'Al pagar la última cuota se firma la escritura y nosotros hacemos la inscripción en el Conservador. Mientras tanto lo que te protege es la promesa firmada ante notario, que ya tiene el precio y la fecha adentro.',
  },
  {
    pregunta: '¿Puedo pagar antes?',
    respuesta:
      'Sí, y no cuesta nada. Puedes abonar cuotas futuras o pagar el saldo completo cuando quieras: al ser cuotas fijas en UF sin interés, pagar antes te adelanta la escritura sin cambiar el total.',
  },
  {
    pregunta: '¿Qué pasa si un mes no puedo pagar?',
    respuesta:
      'Hay diez días de gracia sin recargo. Pasado eso corre el interés corriente, y a los 90 días lo primero que se ofrece es repactar: juntar lo atrasado y repartirlo en hasta 12 cuotas sin cambiar el precio.',
  },
  {
    pregunta: '¿Los gastos operacionales están incluidos?',
    respuesta:
      'Están calculados y escritos en la promesa desde el día que la firmas. Cubren notaría, estudio de títulos e inscripción, y se pagan junto con la escritura al final. No aparecen después.',
  },
];

export default EMPRESA;
