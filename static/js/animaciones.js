/* =============================================================================
   APOFYX — animaciones del sitio

   Todo lo de aca es opcional: si el navegador no soporta IntersectionObserver,
   o si el visitante pidio menos movimiento en su sistema, la pagina se ve igual
   de bien sin ninguna animacion. El menu responsivo lo maneja Bootstrap.
   ========================================================================== */
(function () {
    "use strict";

    var sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var hayObservador = "IntersectionObserver" in window;
    var formatoCL = new Intl.NumberFormat("es-CL");

    /* --- Utilidades --------------------------------------------------------- */

    /** Ejecuta una funcion la primera vez que el elemento entra en pantalla. */
    function alAparecer(elemento, umbral, accion) {
        if (sinMovimiento || !hayObservador) { accion(elemento); return; }
        var obs = new IntersectionObserver(function (entradas) {
            entradas.forEach(function (e) {
                if (!e.isIntersecting) { return; }
                accion(e.target);
                obs.unobserve(e.target);
            });
        }, { threshold: umbral, rootMargin: "0px 0px -50px 0px" });
        obs.observe(elemento);
    }

    /** Cuenta de 0 al destino, desacelerando al final. */
    function contarHasta(el, destino, duracion, retraso) {
        if (isNaN(destino)) { return; }
        var inicio = null;
        var paso = function (ahora) {
            if (inicio === null) { inicio = ahora; }
            var avance = Math.min((ahora - inicio) / duracion, 1);
            var suave = 1 - Math.pow(1 - avance, 3);
            el.textContent = formatoCL.format(Math.round(destino * suave));
            if (avance < 1) { requestAnimationFrame(paso); }
        };
        setTimeout(function () { requestAnimationFrame(paso); }, retraso || 0);
    }

    /* --- 1. Aparicion de bloques al desplazar -------------------------------- */

    document.querySelectorAll(".revelar").forEach(function (el) {
        alAparecer(el, 0.12, function (t) { t.classList.add("es-visible"); });
    });

    /* --- 2. Consola de campana ----------------------------------------------- */

    var consola = document.getElementById("consola");
    if (consola) {
        alAparecer(consola, 0.35, function (t) {
            /* La clase dispara el ancho de las barras, que vive en --pct. */
            t.classList.add("es-visible");
            t.querySelectorAll("[data-progreso]").forEach(function (el, i) {
                var destino = parseInt(el.getAttribute("data-progreso"), 10);
                if (sinMovimiento) {
                    el.textContent = formatoCL.format(destino);
                } else {
                    contarHasta(el, destino, 1100, i * 120);
                }
            });
        });
    }

    /* --- 3. Cifras sueltas de la portada -------------------------------------- */

    document.querySelectorAll("[data-contador]").forEach(function (el) {
        alAparecer(el, 0.5, function (t) {
            var destino = parseInt(t.getAttribute("data-contador"), 10);
            if (sinMovimiento) {
                t.textContent = formatoCL.format(destino);
            } else {
                contarHasta(t, destino, 1100, 0);
            }
        });
    });

    /* --- 4. Cabecera que se afirma al bajar ------------------------------------ */

    var cabecera = document.getElementById("cabecera");
    if (cabecera) {
        var estabaAbajo = null;
        var revisar = function () {
            var abajo = window.scrollY > 20;
            if (abajo !== estabaAbajo) {
                cabecera.classList.toggle("ap-cabecera--desplazada", abajo);
                estabaAbajo = abajo;
            }
        };
        /* passive: true evita que el navegador espere a este manejador para
           poder desplazar la pagina. */
        window.addEventListener("scroll", revisar, { passive: true });
        revisar();
    }
})();
