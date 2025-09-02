from django.test import TestCase, override_settings
from django.db import connection

from inventario.models import Opciones


@override_settings(MIGRATION_MODULES={"inventario": None})
class PasswordFirmaEncryptionTests(TestCase):
    def test_password_firma_is_encrypted_and_decrypted_transparently(self):
        opcion = Opciones.objects.create(
            identificacion="1234567890123",
            razon_social="Empresa",
            direccion_establecimiento="Dir",
            correo="a@b.com",
            telefono="0999999999",
            password_firma="secreto",
        )
        # raw value in DB should not be plain text
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT password_firma FROM inventario_opciones WHERE id=%s", [opcion.id]
            )
            raw = cursor.fetchone()[0]
        assert raw != "secreto"
        # ORM should return decrypted value
        self.assertEqual(Opciones.objects.get(id=opcion.id).password_firma, "secreto")
