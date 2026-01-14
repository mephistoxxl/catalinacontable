"""Generador RIDE (PDF) para Nota de Débito.

Placeholder: se implementará usando el patrón de `nota_credito/ride_generator_nc.py`.
"""

from __future__ import annotations


class RIDENotaDebitoGenerator:
    def __init__(self, nota_debito, opciones):
        self.nd = nota_debito
        self.opciones = opciones

    def generar_pdf(self):
        """Debe devolver un file-like (BytesIO) con PDF (igual que NC).

        Por ahora se deja explícito para evitar confusiones en la vista.
        """
        raise NotImplementedError('Pendiente: generar RIDE para Nota de Débito')
