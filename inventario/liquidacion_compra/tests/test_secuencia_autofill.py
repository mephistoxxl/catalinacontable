from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from inventario.models import Almacen, Empresa, Secuencia, UsuarioEmpresa
from inventario.tenant.queryset import set_current_tenant
from inventario.liquidacion_compra.models import LiquidacionCompra


class LiquidacionSecuenciaAutofillTests(TestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.usuario = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="supersegura123",
        )
        self.empresa = Empresa.objects.create(
            ruc="1234567890123",
            razon_social="Empresa de Prueba",
        )
        set_current_tenant(self.empresa)
        self.addCleanup(lambda: set_current_tenant(None))
        UsuarioEmpresa.all_objects.create(usuario=self.usuario, empresa=self.empresa)
        self.almacen = Almacen.objects.create(
            empresa=self.empresa,
            descripcion="Matriz",
        )
        self.secuencia = Secuencia.objects.create(
            empresa=self.empresa,
            descripcion="Liquidación Compra",
            tipo_documento="03",
            secuencial=5,
            establecimiento=1,
            punto_emision=2,
            activo=True,
        )
        self.client.force_login(self.usuario)
        session = self.client.session
        session["empresa_activa"] = self.empresa.id
        session.save()

    def _detalle_payload(self):
        return {
            "detalles-TOTAL_FORMS": "1",
            "detalles-INITIAL_FORMS": "0",
            "detalles-MIN_NUM_FORMS": "1",
            "detalles-MAX_NUM_FORMS": "1000",
            "detalles-0-id": "",
            "detalles-0-liquidacion": "",
            "detalles-0-producto": "",
            "detalles-0-servicio": "",
            "detalles-0-descripcion": "Servicio de transporte",
            "detalles-0-unidad_medida": "UND",
            "detalles-0-cantidad": "1",
            "detalles-0-costo": "10.00",
            "detalles-0-descuento": "0",
            "detalles-0-codigo_iva": "2",
            "detalles-0-tarifa_iva": "0.1200",
            "detalles-0-valor_iva": "1.20",
            "detalles-0-valor_ice": "0.00",
            "detalles-0-valor_irbp": "0.00",
            "detalles-0-precio_unitario_con_impuestos": "11.200000",
            "detalles-0-total_con_impuestos": "11.20",
            "detalles-0-DELETE": "",
        }

    def _pago_payload(self):
        return {
            "pagos-TOTAL_FORMS": "1",
            "pagos-INITIAL_FORMS": "0",
            "pagos-MIN_NUM_FORMS": "1",
            "pagos-MAX_NUM_FORMS": "1000",
            "pagos-0-id": "",
            "pagos-0-liquidacion": "",
            "pagos-0-forma_pago": "01",
            "pagos-0-total": "10.00",
            "pagos-0-plazo": "",
            "pagos-0-unidad_tiempo": "",
            "pagos-0-DELETE": "",
        }

    def _adicional_payload(self):
        return {
            "adicionales-TOTAL_FORMS": "0",
            "adicionales-INITIAL_FORMS": "0",
            "adicionales-MIN_NUM_FORMS": "0",
            "adicionales-MAX_NUM_FORMS": "15",
        }

    def _build_payload(self, secuencia_info):
        fecha = timezone.localdate().strftime("%Y-%m-%d")
        data = {
            "proveedor": "",
            "almacen": str(self.almacen.pk),
            "fecha_emision": fecha,
            "establecimiento": str(secuencia_info["establecimiento"]),
            "punto_emision": str(secuencia_info["punto_emision"]),
            "secuencia": str(secuencia_info["valor"]),
            "secuencia_config_id": str(secuencia_info["secuencia"].id),
            "concepto": "Compra de productos agrícolas",
            "observaciones": "",
            "sustento_tributario": "01",
            "beneficiario_tipo_identificacion": "05",
            "beneficiario_identificacion": "0912345678",
            "beneficiario_nombre": "Proveedor Demo",
            "beneficiario_direccion": "Calle Falsa 123",
            "beneficiario_correo": "proveedor@example.com",
            "beneficiario_telefono": "0999999999",
            "retencion_iva_porcentaje": "1.0000",
            "retencion_renta_porcentaje": "0.0000",
            "productos_snapshot": "[]",
        }
        data.update(self._detalle_payload())
        data.update(self._pago_payload())
        data.update(self._adicional_payload())
        return data

    def test_get_prefills_sequence_information(self):
        url = reverse("inventario:liquidaciones_compra_crear")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        secuencia_info = response.context["secuencia_info"]
        self.assertIsNotNone(secuencia_info)
        self.assertEqual(secuencia_info["valor"], self.secuencia.secuencial)
        self.assertEqual(secuencia_info["valor_str"], f"{self.secuencia.secuencial:09d}")

        form = response.context["form"]
        self.assertEqual(form.initial["establecimiento"], f"{self.secuencia.establecimiento:03d}")
        self.assertEqual(form.initial["punto_emision"], f"{self.secuencia.punto_emision:03d}")
        self.assertEqual(form.initial["secuencia"], f"{self.secuencia.secuencial:09d}")

    def test_post_creates_liquidacion_and_updates_sequence(self):
        url = reverse("inventario:liquidaciones_compra_crear")
        initial_response = self.client.get(url)
        self.assertEqual(initial_response.status_code, 200)
        secuencia_info = initial_response.context["secuencia_info"]
        payload = self._build_payload(secuencia_info)

        response = self.client.post(url, data=payload)
        self.assertEqual(response.status_code, 302)
        expected_redirect = reverse("inventario:liquidaciones_compra_listar")
        self.assertTrue(response["Location"].endswith(expected_redirect))

        liquidacion = LiquidacionCompra.all_objects.get()
        self.assertEqual(liquidacion.secuencia, secuencia_info["valor"])
        self.assertEqual(liquidacion.establecimiento, secuencia_info["establecimiento"])
        self.assertEqual(liquidacion.punto_emision, secuencia_info["punto_emision"])

        self.secuencia.refresh_from_db()
        self.assertEqual(self.secuencia.secuencial, secuencia_info["valor"])

        siguiente_response = self.client.get(url)
        siguiente_info = siguiente_response.context["secuencia_info"]
        self.assertEqual(siguiente_info["valor"], secuencia_info["valor"] + 1)
        self.assertEqual(siguiente_info["valor_str"], f"{siguiente_info['valor']:09d}")
