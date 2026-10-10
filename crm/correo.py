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

#  Lo que puede ir antes de la arroba (RFC 5322, sin comillas), con puntos al medio y no seguidos.
LOCAL = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*")
#  Etiquetas de letras, numeros y guiones, y una terminacion de letras (o xn-- en un dominio con tildes).
DOMINIO = re.compile(r"([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+([a-z]{2,63}|xn--[a-z0-9-]{1,59})")


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
    if not LOCAL.fullmatch(local) or not DOMINIO.fullmatch(dominio):
        return None
    return f"{local}@{dominio}"
