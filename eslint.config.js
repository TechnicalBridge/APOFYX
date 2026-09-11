/*
 * El linter cubre todo src/ y scripts/: desde la reescritura a DataBridge no queda
 * código generado a máquina en el repo, así que no hay nada que excluir.
 */
import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import hooks from 'eslint-plugin-react-hooks';

export default [
  {
    ignores: ['dist/**', 'docs/**', 'verificacion/**'],
  },

  js.configs.recommended,

  // Código de la aplicación: corre en el navegador.
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { react, 'react-hooks': hooks },
    settings: { react: { version: 'detect' } },
    rules: {
      ...react.configs.recommended.rules,
      ...hooks.configs.recommended.rules,
      // Con el JSX transform moderno no hace falta importar React.
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      eqeqeq: ['error', 'smart'],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
    },
  },

  // Scripts de build y generación: corren en Node, pero el prerender y el arnés
  // llevan adentro funciones que se serializan y se ejecutan en el navegador
  // (page.evaluate), así que ahí conviven los dos vocabularios.
  {
    files: ['scripts/**/*.{js,mjs}', 'vite.config.js', '*.config.js'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: { ...globals.node, ...globals.browser },
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      eqeqeq: ['error', 'smart'],
    },
  },

  // Los tests además usan el vocabulario de Vitest.
  {
    files: ['tests/**/*.{js,mjs}'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: { ...globals.node, ...globals.browser },
    },
  },
];
