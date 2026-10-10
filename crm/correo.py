"""
Un correo que sirve para escribirle al deudor.

Es la misma regla que aplica DataBridge (TB_web, ms-debt `util/Correo`), para que
los dos sistemas acepten y rechacen exactamente las mismas direcciones:

  - acepta cualquier direccion valida: de cualquier proveedor, con `+`, con
    subdominios y con dominios nuevos (`.app`, `.cl`);
  - rechaza lo que no puede recibir correo: sin dominio completo (`juan@gmail`),
    con espacios, sin nada antes de la arroba, con dos arrobas o con puntos
    seguidos.

Es la regla de Django y de Bean Validation, sin las comillas en la parte local
y sin `localhost`: una direccion asi no le llega a un deudor.
"""

import re

#  Se revisa parte por parte, entre puntos, y no con una sola expresion para
#  toda la direccion: asi el tiempo crece en linea recta con el largo, aunque
#  alguien mande "0.0.0.0..." a proposito.

#  Cada parte de lo que va antes de la arroba (RFC 5322, sin comillas).
ATOMO = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+")
#  Cada etiqueta del dominio: letras, numeros y guiones, de 1 a 63.
ETIQUETA = re.compile(r"[a-z0-9-]{1,63}")
#  La terminacion: letras, o xn-- en un dominio con tildes.
TERMINACION = re.compile(r"[a-z]{2,63}|xn--[a-z0-9-]{1,59}")


def normalizar(crudo):
    """
    El correo listo para guardar: sin espacios alrededor y con el dominio en
    minusculas. None si no es una direccion valida.
    """
    if crudo is None:
        return None
    correo = str(crudo).strip()
    if len(correo) > 254 or correo.count("@") != 1 or correo.startswith("@"):
        return None
    local, dominio = correo.split("@")
    dominio = dominio.lower()
    if len(local) > 64 or len(dominio) > 253:
        return None
    #  Puntos al medio y no seguidos: ninguna parte puede quedar vacia.
    if not all(ATOMO.fullmatch(parte) for parte in local.split(".")):
        return None
    *etiquetas, terminacion = dominio.split(".")
    if not etiquetas or not TERMINACION.fullmatch(terminacion):
        return None
    if not all(ETIQUETA.fullmatch(e) and not e.startswith("-") and not e.endswith("-") for e in etiquetas):
        return None
    return f"{local}@{dominio}"
