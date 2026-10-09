<!-- El título va como el commit: tipo(sistema): qué cambia. Por ejemplo: feat(campanas): Campañas desde el portal -->
<!-- Trunk-based: la rama vive uno o dos días y se llama tipo/número-qué (feat/45-descuento-contrato).
     Si el issue es grande, va en varios PRs: los intermedios dicen "Parte de #45" y el último "Closes #45". -->

Closes #

## Qué cambia

<!-- Para quien revisa: qué hace ahora el sistema que antes no hacía, sistema por sistema. -->

## Cómo se probó

<!-- Las pruebas nuevas y el total, y lo que se probó en vivo. Sin claves ni datos reales. -->

## Rollback

<!-- Cómo se deshace si algo sale mal: revertir el PR, una migración, un dato que corregir. -->

## Definition of Done

<!-- La del Informe Fase 2: se marca cada condición que cumple este PR. -->

- [ ] **Cumplimiento funcional:** satisface los criterios de aceptación de su issue.
- [ ] **Verificación:** las pruebas del cambio pasan, y lo relacionado sigue funcionando.
- [ ] **Validación de interfaz:** si cambia pantallas, se recorrió completo en el navegador, en escritorio, en el ancho de un teléfono y en los temas que tenga.
- [ ] **Seguridad:** respeta los permisos, y no trae credenciales, claves ni datos sensibles en el código, la documentación ni las evidencias.
- [ ] **Integración:** sigue siendo compatible con los servicios y contratos que toca, con el manejo de errores y reintentos que corresponda.
- [ ] **Documentación:** el README y los documentos o contratos afectados están al día.
- [ ] **Revisión y entrega:** tiene revisión, pasa la CI y entra a `main` con squash, con la evidencia de su validación en este PR.
