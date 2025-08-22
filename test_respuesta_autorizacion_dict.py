#!/usr/bin/env python3
"""Prueba de procesamiento de respuestas de autorización en formato dict."""
from inventario.sri.sri_client import SRIClient


def test_procesar_dict():
    dummy_client = SRIClient.__new__(SRIClient)
    response = {
        'autorizaciones': {
            'autorizacion': [{
                'estado': 'AUTORIZADO',
                'numeroAutorizacion': '1234567890',
                'fechaAutorizacion': '2025-08-22T13:31:14-05:00',
                'ambiente': 'PRUEBAS',
                'comprobante': '<xml>',
                'mensajes': None,
            }]
        }
    }
    resultado = SRIClient._procesar_respuesta_autorizacion(dummy_client, response)
    print('Estado procesado:', resultado.get('estado'))


if __name__ == '__main__':
    test_procesar_dict()
