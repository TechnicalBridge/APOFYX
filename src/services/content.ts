/*
 * El borde de datos del sitio.
 *
 * POR QUÉ EXISTE ESTA CAPA
 * Hoy todo el contenido vive en `domain/` como constantes. Mañana una parte deja de
 * ser estática: los proyectos, las unidades disponibles y el valor de la UF van a
 * salir de una API. «Quedan 17 de 48» es un número que envejece solo, y el día que
 * lo sirva el backend ninguna sección debería enterarse.
 *
 * Por eso ningún componente importa de `domain/` directamente: pide acá. El día que
 * estas funciones hagan `fetch` en vez de devolver una constante, no hay que tocar
 * ni una pantalla.
 *
 * Lo que sí va a seguir siendo estático —el copy de la empresa, las reglas de la
 * cartera, las preguntas frecuentes— también pasa por acá, para que haya un solo
 * lugar donde mirar de dónde sale cada cosa.
 */
import {
  EMPRESA,
  RAZONES,
  PASOS,
  REGLAS,
  CIFRAS,
  HITOS,
  TESTIMONIOS,
  PREGUNTAS,
  type Empresa,
  type Razon,
  type Paso,
  type Regla,
  type Cifra,
  type Hito,
  type Testimonio,
  type Pregunta,
} from '../domain/company';
import { PROYECTOS, type Proyecto } from '../domain/projects';

/** Identidad de la empresa. Estático siempre: es copy, no datos. */
export const getEmpresa = (): Empresa => EMPRESA;

export const getRazones = (): Razon[] => RAZONES;
export const getPasos = (): Paso[] => PASOS;
export const getReglas = (): Regla[] => REGLAS;
export const getCifras = (): Cifra[] => CIFRAS;
export const getHitos = (): Hito[] => HITOS;
export const getTestimonios = (): Testimonio[] => TESTIMONIOS;
export const getPreguntas = (): Pregunta[] => PREGUNTAS;

/** Todos los proyectos, en el orden en que la empresa los quiere mostrar. */
export const getProyectos = (): Proyecto[] => PROYECTOS;

/** El que abre la portada. Si nadie está marcado, el primero sirve igual. */
export const getDestacado = (): Proyecto => PROYECTOS.find((p) => p.destacado) ?? PROYECTOS[0]!;

export const findProyecto = (slug: string): Proyecto | undefined =>
  PROYECTOS.find((p) => p.slug === slug);

/** Los que todavía se pueden comprar: lo primero que mira quien llega a vender. */
export const getDisponibles = (): Proyecto[] =>
  PROYECTOS.filter((p) => p.estado === 'en-venta' || p.estado === 'en-construccion');

export type { Empresa, Razon, Paso, Regla, Cifra, Hito, Testimonio, Pregunta, Proyecto };
