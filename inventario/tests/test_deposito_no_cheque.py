from django.test import TestCase, RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date
import json

from inventario.views import DetallesFactura
from inventario.models import (
    Cliente,
    Facturador,
    Almacen,
    Factura,
    Producto,
    Banco,
    CampoAdicional,
    Empresa,
)


class DepositoSinCamposChequeTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="usuario", password="pass", email="user@example.com"
        )

        self.empresa = Empresa.objects.create(
            ruc="1234567890123",
            razon_social="Empresa Prueba",
        )
        self.cliente = Cliente.objects.create(
            tipoIdentificacion="05",
            identificacion="0102030405",
            razon_social="Cliente Prueba",
            direccion="Direccion",
            correo="cliente@example.com",
            tipoVenta="1",
            tipoRegimen="1",
            tipoCliente="1",
            empresa=self.empresa,
        )
        self.facturador = Facturador.objects.create(
            nombres="Facturador", correo="facturador@example.com", empresa=self.empresa
        )
        self.almacen = Almacen.objects.create(descripcion="Principal", empresa=self.empresa)
        self.producto = Producto.objects.create(
            codigo="P1",
            codigo_barras="123",
            descripcion="Producto",
            precio=Decimal("10.00"),
            disponible=10,
            categoria="1",
            iva="0",
            costo_actual=Decimal("5.00"),
            empresa=self.empresa,
        )
        self.banco = Banco.objects.create(
            banco="Banco Test",
            titular="Titular",
            numero_cuenta="123456",
            fecha_apertura=date.today(),
            empresa=self.empresa,
        )
        self.factura = Factura.objects.create(
            cliente=self.cliente,
            almacen=self.almacen,
            facturador=self.facturador,
            fecha_emision=date.today(),
            fecha_vencimiento=date.today(),
            establecimiento="001",
            punto_emision="001",
            secuencia="000000001",
            identificacion_cliente=self.cliente.identificacion,
            nombre_cliente=self.cliente.razon_social,
            empresa=self.empresa,
        )

    def _add_session(self, request):
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def test_deposito_no_crea_campos_cheque(self):
        pagos = [
            {
                "sri_pago": "20",
                "tipo": "deposito",
                "monto": "10.00",
                "banco": self.banco.id,
                "comprobante": "ABC123",
            }
        ]
        data = {
            "productos_codigos[]": ["P1"],
            "productos_cantidades[]": ["1"],
            "pagos_efectivo": json.dumps(pagos),
        }
        request = self.factory.post("/detalles/", data)
        request.user = self.user
        request = self._add_session(request)
        request.session["factura_id"] = self.factura.id

        response = DetallesFactura.as_view()(request)
        self.assertEqual(response.status_code, 302)

        self.assertFalse(
            CampoAdicional.objects.filter(
                factura=self.factura, nombre="Banco Cheque"
            ).exists()
        )
        self.assertFalse(
            CampoAdicional.objects.filter(
                factura=self.factura, nombre="Comprobante Cheque"
            ).exists()
        )
        self.assertTrue(
            CampoAdicional.objects.filter(
                factura=self.factura, nombre="Banco Depósito"
            ).exists()
        )
        self.assertTrue(
            CampoAdicional.objects.filter(
                factura=self.factura, nombre="Comprobante Depósito"
            ).exists()
        )
