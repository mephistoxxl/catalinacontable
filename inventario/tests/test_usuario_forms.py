from django.test import TestCase

from inventario.forms import NuevoUsuarioFormulario, UsuarioFormulario
from inventario.models import Usuario


class UsuarioEmailValidationTests(TestCase):
    def setUp(self):
        self.root_user = Usuario.objects.create_user(
            username="root",
            password="password123",
            email="root@example.com",
            nivel=Usuario.ROOT,
        )

    def test_usuario_form_rejects_invalid_email(self):
        form = UsuarioFormulario(
            data={
                "identificacion": "1234567890123",
                "nombre_completo": "Nombre Apellido",
                "email": "correo-invalido",
                "level": str(Usuario.USER),
            },
            user=self.root_user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_nuevo_usuario_form_rejects_invalid_email(self):
        form = NuevoUsuarioFormulario(
            data={
                "identificacion": "1234567890123",
                "nombre_completo": "Nombre Apellido",
                "email": "correo-invalido",
                "password": "claveSegura123",
                "rep_password": "claveSegura123",
                "level": str(Usuario.USER),
            },
            user=self.root_user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_email_is_normalized(self):
        form = NuevoUsuarioFormulario(
            data={
                "identificacion": "1234567890123",
                "nombre_completo": "Nombre Apellido",
                "email": "Usuario@Ejemplo.Com ",
                "password": "claveSegura123",
                "rep_password": "claveSegura123",
                "level": str(Usuario.USER),
            },
            user=self.root_user,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["email"], "usuario@ejemplo.com")
