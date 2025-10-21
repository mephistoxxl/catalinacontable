from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventario.models import Empresa


class EliminarUsuarioViewTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            ruc='1234567890123',
            razon_social='Empresa Test',
            tipo_ambiente='1',
        )
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='pass1234',
        )
        self.admin.empresas.add(self.empresa)
        self.target_user = User.objects.create_user(
            username='objetivo',
            email='objetivo@example.com',
            password='pass1234',
        )
        self.target_user.empresas.add(self.empresa)
        self.url = reverse('inventario:eliminar', args=('usuario', self.target_user.id))

    def _prepare_session(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session['empresa_activa'] = self.empresa.id
        session.save()

    def test_get_request_is_not_allowed(self):
        self._prepare_session()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_post_request_deletes_user(self):
        self._prepare_session()
        response = self.client.post(self.url)
        self.assertRedirects(response, '/inventario/listarUsuarios')
        User = get_user_model()
        self.assertFalse(User.objects.filter(id=self.target_user.id).exists())

