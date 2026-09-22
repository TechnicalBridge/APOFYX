"""
Campos propios.

`Categoria` es el que guarda un estado, un tipo o un origen: valores de una
lista cerrada, conocida al escribir el modelo.
"""

from django.db import models


class Categoria(models.CharField):
    """
    Una categoria cerrada, guardada como ENUM en MySQL.

    POR QUE ENUM Y NO VARCHAR
    Por dentro MySQL guarda un numero de un byte, asi que la tabla y sus
    indices pesan lo mismo que si la columna fuera un TINYINT: medido sobre
    300.000 filas, 5,6 MB de indice contra 7,6 MB. Por fuera se lee y se
    escribe como texto, de modo que una consulta sigue diciendo
    `status = 'paid'` y no `status = 3`, y el contrato de integracion, que
    viaja en texto, no necesita traducir nada.

    POR QUE NO HACE FALTA UN CHECK AL LADO
    El propio ENUM es la restriccion: MySQL rechaza cualquier valor que no
    este en la lista. Un CHECK ademas diria lo mismo dos veces, y dos verdades
    sobre lo mismo terminan separandose.

    EN OTROS MOTORES
    Cae a VARCHAR. La base de pruebas rapida sobre SQLite sigue funcionando, y
    el dia que haya que salir de MySQL el modelo no cambia.
    """

    def db_type(self, connection):
        if connection.vendor == "mysql" and self.choices:
            valores = ", ".join(f"'{valor}'" for valor, _ in self.choices)
            return f"enum({valores})"
        return super().db_type(connection)
