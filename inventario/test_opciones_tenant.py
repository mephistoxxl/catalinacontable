from django.test import TestCase
from inventario.models import Empresa, Opciones
from inventario.tenant.queryset import set_current_tenant


class OpcionesTenantIsolationTests(TestCase):
    def setUp(self):
        self.empresa1 = Empresa.objects.create(ruc="1234567890123", razon_social="Empresa1")
        self.empresa2 = Empresa.objects.create(ruc="9876543210987", razon_social="Empresa2")
        Opciones.objects.create(empresa=self.empresa2, identificacion=self.empresa2.ruc)

    def test_usuario_no_accede_opciones_de_otra_empresa(self):
        set_current_tenant(self.empresa1)
        self.assertIsNone(Opciones.objects.first())
        opciones = Opciones.objects.for_tenant(self.empresa1).first()
        if not opciones:
            opciones = Opciones.objects.create(empresa=self.empresa1, identificacion=self.empresa1.ruc)
        self.assertEqual(Opciones.objects.first().empresa, self.empresa1)
        set_current_tenant(self.empresa2)
        self.assertEqual(Opciones.objects.first().empresa, self.empresa2)
