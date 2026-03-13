from django.test import TestCase

from inventario.models import Almacen, Caja, Empresa, Secuencia


class DefaultSecuenciasTests(TestCase):
    def test_crea_secuencias_base_para_empresa_nueva(self):
        empresa = Empresa.objects.create(
            ruc='1799999999001',
            razon_social='Empresa Secuencias',
        )

        secuencias = Secuencia._unsafe_objects.filter(empresa=empresa).order_by('tipo_documento')

        self.assertEqual(secuencias.count(), 6)

        esperadas = {
            '01': 'Facturas Electrónicas',
            '03': 'Liquidación de Compra Electrónica',
            '04': 'Notas de Crédito Electrónicas',
            '05': 'Notas de Débito Electrónicas',
            '06': 'Guía de Remisión Electrónica',
            '07': 'Retención Electrónica',
        }

        for secuencia in secuencias:
            self.assertEqual(secuencia.descripcion, esperadas[secuencia.tipo_documento])
            self.assertEqual(secuencia.establecimiento, 1)
            self.assertEqual(secuencia.punto_emision, 901)
            self.assertEqual(secuencia.secuencial, 1)
            self.assertEqual(secuencia.get_establecimiento_formatted(), '001')
            self.assertEqual(secuencia.get_punto_emision_formatted(), '901')
            self.assertEqual(secuencia.get_secuencial_formatted(), '000000001')

    def test_crea_almacen_y_caja_por_defecto_para_empresa_nueva(self):
        empresa = Empresa.objects.create(
            ruc='1799999999002',
            razon_social='Empresa Defaults',
        )

        almacen = Almacen._unsafe_objects.filter(
            empresa=empresa,
            descripcion='ALMACEN GENERAL',
            activo=True,
        )
        caja = Caja._unsafe_objects.filter(
            empresa=empresa,
            descripcion='CAJA PRINCIPAL',
            activo=True,
        )

        self.assertEqual(almacen.count(), 1)
        self.assertEqual(caja.count(), 1)