/* =============================================================================
   APOFYX — widget del asistente del sitio

   Habla con /api/chat/ por JSON. La logica de reconocimiento esta en el
   servidor (assistant/engine.py); aca solo se dibuja la conversacion.
   ========================================================================== */
(function () {
    "use strict";

    var boton = document.getElementById("chat-abrir");
    var panel = document.getElementById("chat-panel");
    var hilo = document.getElementById("chat-hilo");
    var form = document.getElementById("chat-form");
    var entrada = document.getElementById("chat-entrada");
    var cerrar = document.getElementById("chat-cerrar");
    var sugerencias = document.getElementById("chat-sugerencias");

    if (!boton || !panel || !hilo || !form || !entrada) { return; }

    var conversacion = null;
    var enviando = false;
    var abierto = false;

    /* --- Token CSRF: Django lo exige en toda peticion que escribe ---------- */

    function tokenCSRF() {
        var campo = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (campo) { return campo.value; }
        var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return m ? m[1] : "";
    }

    /* --- Pintar mensajes --------------------------------------------------- */

    function agregar(texto, quien) {
        var linea = document.createElement("div");
        linea.className = "ap-msj ap-msj--" + quien;
        linea.textContent = texto;
        hilo.appendChild(linea);
        hilo.scrollTop = hilo.scrollHeight;
        return linea;
    }

    function mostrarEscribiendo() {
        var linea = document.createElement("div");
        linea.className = "ap-msj ap-msj--asistente ap-msj--escribiendo";
        linea.innerHTML = "<i></i><i></i><i></i>";
        linea.setAttribute("aria-label", "Escribiendo");
        hilo.appendChild(linea);
        hilo.scrollTop = hilo.scrollHeight;
        return linea;
    }

    /* --- Enviar ------------------------------------------------------------ */

    function enviar(texto) {
        if (enviando || !texto) { return; }
        enviando = true;
        entrada.value = "";
        agregar(texto, "visitante");

        /* Las sugerencias son para partir; una vez que hay conversacion estorban. */
        if (sugerencias) { sugerencias.hidden = true; }

        var escribiendo = mostrarEscribiendo();

        fetch("/api/chat/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": tokenCSRF()
            },
            body: JSON.stringify({ mensaje: texto, conversacion: conversacion })
        })
            .then(function (r) { return r.json(); })
            .then(function (d) {
                escribiendo.remove();
                if (d.ok) {
                    conversacion = d.conversacion;
                    agregar(d.respuesta, "asistente");
                } else {
                    agregar(d.detalle || "No pude procesar su mensaje.", "asistente");
                }
            })
            .catch(function () {
                escribiendo.remove();
                agregar(
                    "No pude conectarme. Puede escribirnos a comercial@apofyx.cl.",
                    "asistente"
                );
            })
            .then(function () {
                enviando = false;
                entrada.focus();
            });
    }

    /* --- Abrir y cerrar ----------------------------------------------------- */

    function abrir() {
        panel.hidden = false;
        abierto = true;
        boton.setAttribute("aria-expanded", "true");
        /* El saludo se pide al servidor, para que salga del catalogo de la base
           y no quede un texto distinto escrito en el JavaScript. */
        if (!hilo.children.length) { enviar("hola"); }
        setTimeout(function () { entrada.focus(); }, 120);
    }

    function ocultar() {
        panel.hidden = true;
        abierto = false;
        boton.setAttribute("aria-expanded", "false");
        boton.focus();
    }

    boton.addEventListener("click", function () {
        if (abierto) { ocultar(); } else { abrir(); }
    });
    if (cerrar) { cerrar.addEventListener("click", ocultar); }

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && abierto) { ocultar(); }
    });

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        enviar(entrada.value.trim());
    });

    if (sugerencias) {
        sugerencias.addEventListener("click", function (e) {
            var chip = e.target.closest("[data-enviar]");
            if (chip) { enviar(chip.getAttribute("data-enviar")); }
        });
    }
})();
