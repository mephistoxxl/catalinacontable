from __future__ import annotations

import json
import os
import stat
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from inventario.models import Empresa, Producto, UsuarioEmpresa


class BackupTmpFileTests(TestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.password = 'adminpass123'
        self.user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password=self.password,
            is_superuser=True,
            is_staff=True,
        )
        self.empresa = Empresa.objects.create(
            ruc='1234567890123',
            razon_social='Empresa Test',
            tipo_ambiente='1',
        )
        UsuarioEmpresa.objects.create(usuario=self.user, empresa=self.empresa)
        self.producto = Producto.objects.create(
            empresa=self.empresa,
            codigo='P001',
            codigo_barras='1234567890123',
            descripcion='Producto de prueba',
            precio=Decimal('10.00'),
            precio2=Decimal('12.00'),
            disponible=5,
            categoria='1',
            iva='2',
            costo_actual=Decimal('5.00'),
        )
        logged_in = self.client.login(username=self.user.username, password=self.password)
        self.assertTrue(logged_in, 'No se pudo iniciar sesión en el cliente de pruebas')

    def _activate_empresa(self) -> None:
        session = self.client.session
        session['empresa_activa'] = self.empresa.id
        session.save()

    def _make_readonly(self, *relative_parts: str) -> Path:
        target = Path(settings.BASE_DIR, *relative_parts)
        target.mkdir(parents=True, exist_ok=True)
        original_mode = stat.S_IMODE(os.lstat(target).st_mode)
        readonly_mode = stat.S_IREAD | stat.S_IEXEC | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
        os.chmod(target, readonly_mode)
        self.addCleanup(lambda path=target, mode=original_mode: os.chmod(path, mode))
        return target

    def test_export_products_uses_tmp_directory(self):
        export_dir = self._make_readonly('inventario', 'tmp')
        self._activate_empresa()
        response = self.client.post(
            reverse('inventario:exportarProductos'),
            {'desde': '2024-01-01', 'hasta': '2024-12-31'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename="productos.json"',
        )

        payload = b''.join(response.streaming_content)
        data = json.loads(payload.decode('utf-8'))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['pk'], self.producto.pk)
        self.assertFalse((export_dir / 'productos.json').exists())

    def test_dumpdata_uses_tmp_directory(self):
        backup_dir = self._make_readonly('inventario', 'archivos', 'tmp')
        self._activate_empresa()
        response = self.client.get(reverse('inventario:descargarBDD'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename="inventario_respaldo.xml"',
        )
        content = b''.join(response.streaming_content)
        self.assertIn(b'<django-objects', content)
        self.assertFalse((backup_dir / 'inventario_respaldo.xml').exists())

    def test_import_uses_tmp_directory(self):
        bdd_dir = self._make_readonly('inventario', 'archivos', 'BDD')
        self._activate_empresa()
        uploaded = SimpleUploadedFile('fixture.json', b'[]', content_type='application/json')

        response = self.client.post(
            reverse('inventario:importarBDD'),
            {'archivo': uploaded},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse((bdd_dir / 'inventario_respaldo.xml').exists())
