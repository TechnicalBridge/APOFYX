"""
El RUT: normalizarlo y verificar su digito verificador.

Vive en crm porque es la llave con la que una empresa o una persona se
identifican en todo el sistema, y la usan tanto el panel como la recepcion de
cartera.

Dos cosas distintas que conviene no confundir:

  normalizar()   deja el RUT en su forma canonica: sin puntos, con guion y con
                 la K en mayuscula. Es lo que hace que el UNIQUE funcione,
                 porque '76.543.210-3' y '76543210-3' son el mismo RUT.

  es_valido()    revisa el digito verificador con el modulo 11. Un RUT puede
                 tener el formato perfecto y no existir: eso lo detecta solo
                 esta funcion, y es lo que evita mandar a cobrar a un RUT que
                 cualquier otro sistema va a rechazar.
"""

import re

CANONICO = re.compile(r"^\d{7,8}-[\dK]$")


def normalizar(crudo):
    """'76.543.210-3', '765432103' y '76543210-3' quedan todos iguales."""
    limpio = (crudo or "").strip().upper().replace(".", "").replace(" ", "")
    if "-" not in limpio and len(limpio) > 1:
        limpio = f"{limpio[:-1]}-{limpio[-1]}"
    return limpio


def tiene_formato(rut):
    return bool(CANONICO.match(rut or ""))


def digito_verificador(cuerpo):
    """Modulo 11: se pondera de derecha a izquierda con 2,3,4,5,6,7 y se repite."""
    suma, factor = 0, 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return {11: "0", 10: "K"}.get(resto, str(resto))


def es_valido(rut):
    """Formato correcto y digito verificador que corresponde."""
    normalizado = normalizar(rut)
    if not tiene_formato(normalizado):
        return False
    cuerpo, guion, verificador = normalizado.partition("-")
    return digito_verificador(cuerpo) == verificador
