"""Generador XML para Nota de Débito (SRI codDoc 05).

Placeholder: se implementará con el XSD oficial del SRI.
"""

from __future__ import annotations


class XMLGeneratorNotaDebito:
    def __init__(self, nota_debito, opciones):
        self.nd = nota_debito
        self.opciones = opciones

    def generar_clave_acceso(self) -> str:
        raise NotImplementedError('Pendiente: generar clave de acceso para Nota de Débito')

    def generar_xml(self) -> str:
        raise NotImplementedError('Pendiente: generar XML Nota de Débito')
