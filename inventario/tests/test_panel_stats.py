from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date

from inventario.models import (
    Empresa,
    UsuarioEmpresa,
    Producto,
    Cliente,
    Factura,
    Facturador,
    Almacen,
)


@override_settings(MIGRATION_MODULES={'inventario': None})
class PanelStatsPerEmpresaTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="mainuser", password="pass", email="main@example.com"
        )
        self.user_emp1 = User.objects.create_user(
            username="user1", password="pass", email="u1@example.com"
        )
        self.user_emp2 = User.objects.create_user(
            username="user2", password="pass", email="u2@example.com"
        )

        self.empresa1 = Empresa.objects.create(
            ruc="1111111111111", razon_social="Empresa 1"
        )
        self.empresa2 = Empresa.objects.create(
            ruc="2222222222222", razon_social="Empresa 2"
        )

        UsuarioEmpresa.objects.create(usuario=self.user, empresa=self.empresa1)
        UsuarioEmpresa.objects.create(usuario=self.user, empresa=self.empresa2)
        UsuarioEmpresa.objects.create(usuario=self.user_emp1, empresa=self.empresa1)
        UsuarioEmpresa.objects.create(usuario=self.user_emp2, empresa=self.empresa2)

        # Almacenes y facturadores
        self.almacen1 = Almacen.objects.create(descripcion="A1", empresa=self.empresa1)
        self.almacen2 = Almacen.objects.create(descripcion="A2", empresa=self.empresa2)
        self.facturador1 = Facturador.objects.create(
            nombres="F1", correo="f1@example.com", empresa=self.empresa1
        )
        self.facturador2 = Facturador.objects.create(
            nombres="F2", correo="f2@example.com", empresa=self.empresa2
        )

        # Productos
        Producto.objects.create(
            codigo="P1",
            codigo_barras="111",
            descripcion="Prod1",
            precio=Decimal("10.00"),
            disponible=10,
            categoria="1",
            iva="0",
            costo_actual=Decimal("5.00"),
            empresa=self.empresa1,
        )
        Producto.objects.create(
            codigo="P2",
            codigo_barras="222",
            descripcion="Prod2",
            precio=Decimal("20.00"),
            disponible=10,
            categoria="1",
            iva="0",
            costo_actual=Decimal("10.00"),
            empresa=self.empresa2,
        )
        Producto.objects.create(
            codigo="P3",
            codigo_barras="333",
            descripcion="Prod3",
            precio=Decimal("30.00"),
            disponible=10,
            categoria="1",
            iva="0",
            costo_actual=Decimal("15.00"),
            empresa=self.empresa2,
        )

        # Clientes
        self.cliente1 = Cliente.objects.create(
            tipoIdentificacion="05",
            identificacion="0102030401",
            razon_social="Cli1",
            direccion="Dir",
            correo="c1@example.com",
            tipoVenta="1",
            tipoRegimen="1",
            tipoCliente="1",
            empresa=self.empresa1,
        )
        self.cliente2 = Cliente.objects.create(
            tipoIdentificacion="05",
            identificacion="0102030402",
            razon_social="Cli2",
            direccion="Dir",
            correo="c2@example.com",
            tipoVenta="1",
            tipoRegimen="1",
            tipoCliente="1",
            empresa=self.empresa2,
        )
        self.cliente3 = Cliente.objects.create(
            tipoIdentificacion="05",
            identificacion="0102030403",
            razon_social="Cli3",
            direccion="Dir",
            correo="c3@example.com",
            tipoVenta="1",
            tipoRegimen="1",
            tipoCliente="1",
            empresa=self.empresa2,
        )

        # Facturas
        Factura.objects.create(
            empresa=self.empresa1,
            cliente=self.cliente1,
            almacen=self.almacen1,
            facturador=self.facturador1,
            fecha_emision=date.today(),
            fecha_vencimiento=date.today(),
            establecimiento="001",
            punto_emision="001",
            secuencia="000000001",
            identificacion_cliente=self.cliente1.identificacion,
            nombre_cliente=self.cliente1.razon_social,
            monto_general=Decimal("100.00"),
        )
        Factura.objects.create(
            empresa=self.empresa2,
            cliente=self.cliente2,
            almacen=self.almacen2,
            facturador=self.facturador2,
            fecha_emision=date.today(),
            fecha_vencimiento=date.today(),
            establecimiento="001",
            punto_emision="001",
            secuencia="000000002",
            identificacion_cliente=self.cliente2.identificacion,
            nombre_cliente=self.cliente2.razon_social,
            monto_general=Decimal("200.00"),
        )
        Factura.objects.create(
            empresa=self.empresa2,
            cliente=self.cliente3,
            almacen=self.almacen2,
            facturador=self.facturador2,
            fecha_emision=date.today(),
            fecha_vencimiento=date.today(),
            establecimiento="001",
            punto_emision="001",
            secuencia="000000003",
            identificacion_cliente=self.cliente3.identificacion,
            nombre_cliente=self.cliente3.razon_social,
            monto_general=Decimal("300.00"),
        )

    def _get_panel_context(self, empresa):
        client = Client()
        client.force_login(self.user)
        session = client.session
        session['empresa_activa'] = empresa.id
        session.save()
        response = client.get('/inventario/panel')
        return response.context

    def test_panel_shows_stats_for_active_company(self):
        ctx = self._get_panel_context(self.empresa1)
        self.assertEqual(ctx['productosRegistrados'], 1)
        self.assertEqual(ctx['clientesRegistrados'], 1)
        self.assertEqual(ctx['usuariosRegistrados'], 2)
        self.assertEqual(ctx['facturasEmitidas'], 1)

        ctx2 = self._get_panel_context(self.empresa2)
        self.assertEqual(ctx2['productosRegistrados'], 2)
        self.assertEqual(ctx2['clientesRegistrados'], 2)
        self.assertEqual(ctx2['usuariosRegistrados'], 2)
        self.assertEqual(ctx2['facturasEmitidas'], 2)
