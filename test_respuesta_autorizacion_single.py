from inventario.sri.sri_client import SRIClient


def test_procesar_autorizacion_unica():
    dummy_client = SRIClient.__new__(SRIClient)
    response = {
        'autorizaciones': {
            'autorizacion': {
                'estado': 'AUTORIZADO',
                'numeroAutorizacion': '1234567890',
                'fechaAutorizacion': '2025-08-22T13:31:14-05:00',
                'ambiente': 'PRUEBAS',
                'comprobante': '<xml>',
                'mensajes': None,
            }
        }
    }
    resultado = SRIClient._procesar_respuesta_autorizacion(dummy_client, response)
    assert resultado.get('estado') == 'AUTORIZADO'
