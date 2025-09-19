import os
import shutil
import tempfile
from datetime import date

from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from inventario.models import Empresa, Opciones, Usuario


class FirmaElectronicaViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tempdir)
        self.override = override_settings(FIRMAS_ROOT=self.tempdir)
        self.override.enable()
        self.addCleanup(self.override.disable)

        self.empresa = Empresa.objects.create(
            ruc="1234567890123",
            razon_social="Empresa Test",
        )

        self.user = Usuario.objects.create_user(
            username="9999999999999",
            email="user@example.com",
            password="pass",
        )
        self.user.first_name = "Nombre"
        self.user.last_name = "Apellido"
        self.user.save()
        self.user.empresas.add(self.empresa)
        self.client.force_login(self.user)

        session = self.client.session
        session["empresa_activa"] = self.empresa.id
        session.save()

        self.opciones = Opciones.objects.create(
            empresa=self.empresa,
            identificacion=self.empresa.ruc,
            correo="correo@example.com",
            obligado="SI",
            tipo_emision="1",
            mensaje_factura="Mensaje inicial",
            tipo_ambiente="1",
        )

        self.opciones.firma_electronica.save(
            "firma-test.p12",
            ContentFile(b"dummy file"),
            save=True,
        )
        self.original_file_name = self.opciones.firma_electronica.name
        self.original_password = "super-secret"
        self.opciones.password_firma = self.original_password
        self.opciones.fecha_caducidad_firma = date.today()
        self.opciones.save()

    def test_password_and_file_preserved_when_not_provided(self):
        url = reverse("inventario:firma_electronica")

        response = self.client.post(
            url,
            data={
                "tipo_ambiente": "2",
                "tipo_emision": self.opciones.tipo_emision,
                "numero_contribuyente_especial": self.opciones.numero_contribuyente_especial or "",
                "fecha_caducidad_firma": self.opciones.fecha_caducidad_firma.strftime("%Y-%m-%d"),
                "password_firma": "",
                "obligado": self.opciones.obligado,
                "correo": self.opciones.correo,
                "mensaje_factura": self.opciones.mensaje_factura or "",
            },
        )

        self.assertEqual(response.status_code, 200)

        opciones = Opciones.objects.for_tenant(self.empresa).get(pk=self.opciones.pk)
        self.assertEqual(opciones.tipo_ambiente, "2")
        self.assertEqual(opciones.password_firma, self.original_password)
        self.assertEqual(opciones.firma_electronica.name, self.original_file_name)
        self.assertTrue(os.path.exists(os.path.join(self.tempdir, self.original_file_name)))
