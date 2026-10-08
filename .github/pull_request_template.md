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

- [ ] Cumple el criterio de aceptación del issue.
- [ ] Trae sus pruebas, y todas pasan en local y en la CI.
- [ ] Si toca pantallas: probado en el navegador completando cada acción y en el ancho de un celular.
- [ ] El README y el contrato de integración están al día si cambia algo que otro sistema usa.
- [ ] Ningún secreto ni clave en el código, en el README ni en los commits.
- [ ] La rama salió de main hace uno o dos días y está al día con main.
- [ ] Se mergea con squash, con el título del PR.
