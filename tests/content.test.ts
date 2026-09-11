import fs from 'node:fs';

import { describe, it, expect } from 'vitest';

import {
  EMPRESA,
  RAZONES,
  PASOS,
  REGLAS,
  CIFRAS,
  HITOS,
  TESTIMONIOS,
  PREGUNTAS,
} from '../src/domain/company.ts';
import { PROYECTOS } from '../src/domain/projects.ts';
import { cotizar, PIE_MINIMO, PLAZOS } from '../src/domain/financing.ts';
import { CREDITOS } from '../src/domain/photo-credits.ts';
import { RUTAS } from '../scripts/rutas.ts';

/*
 * DataBridge es una empresa inventada, y eso tiene que seguir siendo cierto y
 * visible. Estas comprobaciones protegen tres cosas: que el contenido ficticio esté
 * completo, que la aritmética del financiamiento no mienta —es lo único del sitio
 * que calcula plata— y que no quede rastro del proyecto anterior.
 */

const todoElTexto = JSON.stringify({
  EMPRESA,
  RAZONES,
  PASOS,
  REGLAS,
  CIFRAS,
  HITOS,
  TESTIMONIOS,
  PREGUNTAS,
  PROYECTOS,
}).toLowerCase();

describe('la empresa', () => {
  it('no menciona el proyecto anterior ni a sus personas', () => {
    expect(todoElTexto).not.toContain('kobra');
    expect(todoElTexto).not.toContain('carolina');
    expect(todoElTexto).not.toContain('terravista');
  });

  it('es una inmobiliaria con datos de contacto completos', () => {
    expect(EMPRESA.nombre).toBe('DataBridge');
    expect(EMPRESA.rubro).toBe('Inmobiliaria');
    expect(EMPRESA.promesa.length).toBeGreaterThan(15);
    expect(EMPRESA.bajada.length).toBeGreaterThan(80);
    for (const correo of [EMPRESA.correo, EMPRESA.correoVentas]) {
      expect(correo).toMatch(/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/);
    }
  });

  /*
   * Este sitio es el de la inmobiliaria, no el de la plataforma de pagos que se
   * construye aparte. La distinción se borra fácil —ambas hablan de cuotas— así que
   * queda escrita: acá no se vende software.
   *
   * Ojo: «gastos de cobranza» sí aparece, y está bien. Es el término legal correcto
   * para lo que un acreedor puede o no cobrar, y la empresa lo usa para decir que
   * no los cobra. Lo que se vigila es el discurso de producto, no la palabra.
   */
  it('no vende software de cobranza: ese es otro proyecto', () => {
    for (const frase of [
      'inteligencia artificial',
      'agente de cobranza',
      'cartera de clientes',
      'plataforma',
      'integración',
    ]) {
      expect(todoElTexto).not.toContain(frase);
    }
  });
});

describe('proyectos', () => {
  it('tienen slug único y ficha completa', () => {
    const slugs = PROYECTOS.map((p) => p.slug);
    expect(new Set(slugs).size).toBe(slugs.length);

    for (const p of PROYECTOS) {
      expect(p.slug).toMatch(/^[a-z0-9-]+$/);
      expect(p.nombre.length).toBeGreaterThan(3);
      expect(p.comuna.length).toBeGreaterThan(3);
      expect(p.resumen.length).toBeGreaterThan(30);
      expect(p.descripcion.length).toBeGreaterThan(0);
      expect(p.atributos.length).toBeGreaterThan(2);
      expect(p.desdeUF).toBeGreaterThan(0);
    }
  });

  it('nunca hay más disponibles que unidades', () => {
    for (const p of PROYECTOS) {
      expect(p.disponibles).toBeGreaterThanOrEqual(0);
      expect(p.disponibles).toBeLessThanOrEqual(p.unidades);
    }
  });

  it('el plazo de cada proyecto es uno de los que ofrece la empresa', () => {
    for (const p of PROYECTOS) {
      expect(PLAZOS).toContain(p.plazoMaximo);
    }
  });

  it('hay exactamente un destacado, porque la portada muestra uno', () => {
    expect(PROYECTOS.filter((p) => p.destacado)).toHaveLength(1);
  });

  it('lo que todavía no se vende no aparece como vendido', () => {
    for (const p of PROYECTOS.filter((x) => x.estado === 'proximamente')) {
      expect(p.disponibles).toBe(p.unidades);
    }
  });
});

/*
 * Las fotos son de terceros bajo licencia Creative Commons, que obliga a atribuir.
 * Si alguien agrega una imagen y olvida su crédito, el sitio queda incumpliendo la
 * licencia en silencio; esto lo convierte en un test rojo.
 */
describe('fotos', () => {
  it('cada proyecto tiene al menos una foto con pie', () => {
    for (const p of PROYECTOS) {
      expect(p.fotos.length).toBeGreaterThan(0);
      for (const f of p.fotos) {
        expect(f.archivo).toMatch(/^[a-z0-9-]+\.jpg$/);
        expect(f.pie.length).toBeGreaterThan(10);
      }
    }
  });

  it('el archivo de cada foto existe en public/fotos', () => {
    for (const p of PROYECTOS) {
      for (const f of p.fotos) {
        expect(fs.existsSync(`public/fotos/${f.archivo}`), f.archivo).toBe(true);
      }
    }
  });

  it('cada foto usada está acreditada', () => {
    const acreditadas = new Set(CREDITOS.map((c) => c.archivo));
    for (const p of PROYECTOS) {
      for (const f of p.fotos) expect(acreditadas, f.archivo).toContain(f.archivo);
    }
  });

  it('cada crédito nombra autor y licencia', () => {
    for (const c of CREDITOS) {
      expect(c.autor.length).toBeGreaterThan(1);
      expect(c.licencia).toMatch(/^(BY|BY-SA|CC0|PDM)$/);
      expect(c.origen).toMatch(/^https?:\/\//);
    }
  });
});

describe('financiamiento', () => {
  it('el pie más las cuotas dan el precio, sin centavos perdidos', () => {
    for (const p of PROYECTOS) {
      const c = cotizar({ precioUF: p.desdeUF, meses: p.plazoMaximo });
      expect(c.pieUF + c.cuotaUF * c.meses).toBeCloseTo(p.desdeUF, 6);
    }
  });

  it('alargar el plazo baja la cuota y no cambia el total', () => {
    const corto = cotizar({ precioUF: 1200, meses: 36 });
    const largo = cotizar({ precioUF: 1200, meses: 60 });
    expect(largo.cuotaUF).toBeLessThan(corto.cuotaUF);
    expect(largo.saldoUF).toBe(corto.saldoUF);
  });

  it('subir el pie baja la cuota', () => {
    const minimo = cotizar({ precioUF: 1200, pie: PIE_MINIMO, meses: 48 });
    const alto = cotizar({ precioUF: 1200, pie: 0.5, meses: 48 });
    expect(alto.cuotaUF).toBeLessThan(minimo.cuotaUF);
  });

  it('un plazo de cero no devuelve infinito', () => {
    expect(Number.isFinite(cotizar({ precioUF: 1200, meses: 0 }).cuotaUF)).toBe(true);
  });
});

describe('rutas', () => {
  it('hay una ruta por proyecto y ninguna del sitio anterior', () => {
    for (const p of PROYECTOS) {
      expect(RUTAS).toContain(`/proyectos/${p.slug}`);
    }
    for (const r of RUTAS) {
      expect(r).not.toMatch(/verificacion|precios|seguridad|casos|como-funciona/);
    }
  });

  it('no se repiten', () => {
    expect(new Set(RUTAS).size).toBe(RUTAS.length);
  });
});
