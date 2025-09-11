from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

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
        self.staff_user = get_user_model().objects.create_user(
            username="staff", email="staff@example.com", password="pass"
        )
        self.staff_user.is_staff = True
        self.staff_user.save()
        self.staff_user.empresas.add(self.empresa)
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

    def test_staff_excluded_from_queryset(self):
        request = self.factory.get("/")
        request.tenant = self.empresa
        qs = self.usuario_admin.get_queryset(request)
        self.assertIn(self.user, qs)
        self.assertNotIn(self.staff_user, qs)


class UsuarioAdminPermissionsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.empresa1 = Empresa.objects.create(
            ruc="1234567890123", razon_social="Tenant1"
        )
        self.empresa2 = Empresa.objects.create(
            ruc="9876543210987", razon_social="Tenant2"
        )
        User = get_user_model()
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@example.com", password="pass"
        )
        self.admin_user.is_staff = True
        self.admin_user.save()
        perms = Permission.objects.filter(
            codename__in=["change_usuario", "delete_usuario"]
        )
        self.admin_user.user_permissions.set(perms)
        self.admin_user.empresas.add(self.empresa1)

        self.staff_obj = User.objects.create_user(
            username="staff_obj", email="staffobj@example.com", password="pass"
        )
        self.staff_obj.is_staff = True
        self.staff_obj.save()
        self.staff_obj.empresas.add(self.empresa1)

        self.superuser_obj = User.objects.create_superuser(
            username="super_obj", email="superobj@example.com", password="pass"
        )
        self.superuser_obj.empresas.add(self.empresa1)

        self.user_empresa1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="pass"
        )
        self.user_empresa1.empresas.add(self.empresa1)

        self.user_empresa2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="pass"
        )
        self.user_empresa2.empresas.add(self.empresa2)

        self.usuario_admin = UsuarioAdmin(User, tenant_admin_site)

    def _get_request(self):
        request = self.factory.get("/")
        request.user = self.admin_user
        request.tenant = self.empresa1
        return request

    def test_hidden_fields_and_empresas_locked(self):
        request = self._get_request()
        form_class = self.usuario_admin.get_form(request)
        form = form_class()
        self.assertNotIn("is_superuser", form.fields)
        self.assertNotIn("groups", form.fields)
        self.assertNotIn("user_permissions", form.fields)
        empresas_field = form.fields["empresas"]
        self.assertTrue(empresas_field.disabled)
        self.assertEqual(list(empresas_field.queryset), [self.empresa1])

    def test_save_model_assigns_current_tenant(self):
        request = self._get_request()
        User = get_user_model()
        new_user = User.objects.create_user(
            username="nuevo", email="nuevo@example.com", password="pass"
        )
        new_user.empresas.add(self.empresa2)
        self.usuario_admin.save_model(request, new_user, form=None, change=False)
        self.assertEqual(list(new_user.empresas.all()), [self.empresa1])

    def test_change_permission_respects_empresa(self):
        request = self._get_request()
        self.assertTrue(
            self.usuario_admin.has_change_permission(request, obj=self.user_empresa1)
        )
        self.assertFalse(
            self.usuario_admin.has_change_permission(request, obj=self.user_empresa2)
        )

    def test_delete_permission_respects_empresa(self):
        request = self._get_request()
        self.assertTrue(
            self.usuario_admin.has_delete_permission(request, obj=self.user_empresa1)
        )
        self.assertFalse(
            self.usuario_admin.has_delete_permission(request, obj=self.user_empresa2)
        )

    def test_cannot_modify_staff_user(self):
        request = self._get_request()
        self.assertFalse(
            self.usuario_admin.has_change_permission(request, obj=self.staff_obj)
        )
        self.assertFalse(
            self.usuario_admin.has_delete_permission(request, obj=self.staff_obj)
        )

    def test_cannot_modify_superuser(self):
        request = self._get_request()
        self.assertFalse(
            self.usuario_admin.has_change_permission(request, obj=self.superuser_obj)
        )
        self.assertFalse(
            self.usuario_admin.has_delete_permission(request, obj=self.superuser_obj)
        )
