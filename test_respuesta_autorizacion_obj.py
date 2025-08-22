#!/usr/bin/env python3
"""Prueba de procesamiento de respuestas de autorización en formato objeto."""
from inventario.sri.sri_client import SRIClient


class DummyAutorizaciones:
    def __init__(self, autorizaciones):
        self.autorizacion = autorizaciones


class DummyResponse:
    def __init__(self, autorizaciones):
        self.autorizaciones = autorizaciones


def test_procesar_obj():
    dummy_client = SRIClient.__new__(SRIClient)
    aut = {
        'estado': 'AUTORIZADO',
        'numeroAutorizacion': '1234567890',
        'fechaAutorizacion': '2025-08-22T13:31:14-05:00',
        'ambiente': 'PRUEBAS',
        'comprobante': '<xml>',
        'mensajes': None,
    }
    response = DummyResponse(DummyAutorizaciones([aut]))
    resultado = SRIClient._procesar_respuesta_autorizacion(dummy_client, response)
    assert resultado.get('estado') == 'AUTORIZADO'
