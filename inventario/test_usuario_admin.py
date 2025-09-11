from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model

from .admin import UsuarioAdmin, tenant_admin_site
from .models import Empresa


class UsuarioAdminQuerysetTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.empresa = Empresa.objects.create(
            ruc="1234567890123", razon_social="Tenant"
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="super", email="super@example.com", password="pass"
        )
        self.superuser.empresas.add(self.empresa)
        self.user = get_user_model().objects.create_user(
            username="normal", email="user@example.com", password="pass"
        )
        self.user.empresas.add(self.empresa)
        self.usuario_admin = UsuarioAdmin(get_user_model(), tenant_admin_site)

    def test_superuser_excluded_from_queryset(self):
        request = self.factory.get("/")
        request.tenant = self.empresa
        qs = self.usuario_admin.get_queryset(request)
        self.assertIn(self.user, qs)
        self.assertNotIn(self.superuser, qs)
