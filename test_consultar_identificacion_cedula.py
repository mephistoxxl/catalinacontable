import json
import requests
from services import consultar_identificacion


class DummyResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.headers = {}
        self.url = "https://example.com"

    @property
    def text(self):
        return json.dumps(self._data)

    def json(self):
        return self._data


def test_no_regimen_for_cedula(monkeypatch):
    """La consulta de una cédula no debe modificar el tipo de régimen."""

    def fake_get(url, params, timeout):
        data = {
            "tipoContribuyente": "RIMPE - EMPRENDEDORES",
            "calleDomicilio": "Av. Siempre Viva",
            "razonSocial": "Persona Test",
            "obligadoLlevarContabilidad": "NO",
            "estado": "ACTIVO",
        }
        return DummyResponse(data)

    monkeypatch.setattr(requests, "get", fake_get)

    resultado = consultar_identificacion("1234567890")  # 10 dígitos -> CÉDULA

    assert resultado["tipo_identificacion"] == "CEDULA"
    assert "tipo_regimen" not in resultado
