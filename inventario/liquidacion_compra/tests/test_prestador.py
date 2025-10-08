from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from inventario.models import Almacen, Empresa
from inventario.tenant.queryset import set_current_tenant
from inventario.liquidacion_compra.forms import LiquidacionCompraForm
from inventario.liquidacion_compra.models import Prestador


class PrestadorFormIntegrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(username="tester", password="pass12345")
        self.empresa = Empresa.objects.create(
            ruc="1234567890123",
            razon_social="Empresa de Prueba",
        )
        set_current_tenant(self.empresa)
        self.addCleanup(lambda: set_current_tenant(None))
        self.almacen = Almacen.objects.create(
            empresa=self.empresa,
            descripcion="Principal",
        )

    def test_guardar_prestador_crea_registro(self):
        datos_formulario = {
            "beneficiario_tipo_identificacion": "05",
            "beneficiario_identificacion": "0912345678",
            "beneficiario_nombre": "Juan Perez",
            "beneficiario_direccion": "Av. Siempre Viva",
            "beneficiario_correo": "juan@example.com",
            "beneficiario_telefono": "0999999999",
            "fecha_emision": timezone.localdate().strftime("%Y-%m-%d"),
            "almacen": str(self.almacen.pk),
            "establecimiento": "1",
            "punto_emision": "1",
            "secuencia": "1",
            "concepto": "Compra de artesanías",
            "observaciones": "",
            "sustento_tributario": "01",
        }

        formulario = LiquidacionCompraForm(data=datos_formulario, empresa=self.empresa)
        self.assertTrue(formulario.is_valid(), formulario.errors)

        liquidacion = formulario.save(commit=False)
        liquidacion.empresa = self.empresa
        liquidacion.usuario_creacion = self.usuario
        liquidacion.estado = "BORRADOR"
        liquidacion.save()

        prestador = formulario.guardar_prestador(liquidacion)

        self.assertIsNotNone(prestador)
        self.assertEqual(Prestador.objects.count(), 1)
        self.assertEqual(prestador.liquidacion, liquidacion)
        self.assertEqual(prestador.identificacion, datos_formulario["beneficiario_identificacion"])
        self.assertEqual(prestador.nombre, datos_formulario["beneficiario_nombre"])
        self.assertEqual(prestador.proveedor, liquidacion.proveedor)
        self.assertEqual(prestador.direccion, datos_formulario["beneficiario_direccion"])
        self.assertEqual(prestador.correo, datos_formulario["beneficiario_correo"])
        self.assertEqual(prestador.telefono, datos_formulario["beneficiario_telefono"])
