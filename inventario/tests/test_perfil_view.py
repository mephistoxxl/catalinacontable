from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from inventario.models import Empresa, Usuario


class PerfilEmpresaRestrictionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.empresa_a = Empresa.objects.create(
            ruc="1111111111111",
            razon_social="Empresa A",
        )
        self.empresa_b = Empresa.objects.create(
            ruc="2222222222222",
            razon_social="Empresa B",
        )

        self.admin_user = Usuario.objects.create_user(
            username="1000000000000",
            email="admin@example.com",
            password="pass",
        )
        self.admin_user.nivel = Usuario.ADMIN
        # La vista exige superusuario para editar otros perfiles
        self.admin_user.is_superuser = True
        self.admin_user.first_name = "Admin"
        self.admin_user.save()
        self.admin_user.empresas.add(self.empresa_a)

        self.target_user = Usuario.objects.create_user(
            username="2000000000000",
            email="target@example.com",
            password="pass",
        )
        self.target_user.nivel = Usuario.USER
        self.target_user.first_name = "Target"
        self.target_user.save()
        self.target_user.empresas.add(self.empresa_a)

    def test_admin_only_sees_managed_empresas(self):
        self.client.force_login(self.admin_user)
        url = reverse("inventario:perfil", args=("editar", self.target_user.id))

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(list(form.fields["empresa"].queryset), [self.empresa_a])

        response = self.client.post(
            url,
            data={
                "identificacion": self.target_user.username,
                "nombre_completo": "Target Persona",
                "email": self.target_user.email,
                "level": str(Usuario.USER),
                "empresa": str(self.empresa_b.id),
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("Select a valid choice", form.errors["empresa"][0])

        self.target_user.refresh_from_db()
        self.assertEqual(list(self.target_user.empresas.all()), [self.empresa_a])


class PerfilSuperadminTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.empresa_a = Empresa.objects.create(
            ruc="3333333333333",
            razon_social="Empresa Root A",
        )
        self.empresa_b = Empresa.objects.create(
            ruc="4444444444444",
            razon_social="Empresa Root B",
        )

        self.superadmin = Usuario.objects.create_user(
            username="3000000000000",
            email="root@example.com",
            password="pass",
        )
        self.superadmin.nivel = Usuario.ROOT
        self.superadmin.is_superuser = True
        self.superadmin.first_name = "Root"
        self.superadmin.save()
        self.superadmin.empresas.add(self.empresa_a)

    def test_superadmin_can_edit_with_all_empresas(self):
        self.client.force_login(self.superadmin)
        url = reverse("inventario:perfil", args=("editar", self.superadmin.id))

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertCountEqual(
            form.fields["empresa"].queryset,
            Empresa.objects.all(),
        )

        response = self.client.post(
            url,
            data={
                "identificacion": self.superadmin.username,
                "nombre_completo": "Root Actualizado",
                "email": self.superadmin.email,
                "empresa": str(self.empresa_b.id),
            },
        )
        self.assertEqual(response.status_code, 302)

        self.superadmin.refresh_from_db()
        self.assertEqual(self.superadmin.first_name, "Root Actualizado")
        self.assertEqual(list(self.superadmin.empresas.all()), [self.empresa_b])


class PerfilPasswordChangeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.usuario = Usuario.objects.create_user(
            username="4000000000000",
            email="usuario@example.com",
            password="ClaveVieja123",
        )
        self.usuario.nivel = Usuario.ROOT
        self.usuario.is_superuser = True
        self.usuario.save()

    def test_rejects_wrong_current_password(self):
        self.client.force_login(self.usuario)
        url = reverse("inventario:perfil", args=("clave", self.usuario.id))
        response = self.client.post(
            url,
            data={
                "clave_actual": "ClaveIncorrecta",
                "clave_nueva": "NuevaClaveSegura123",
                "repetir_clave": "NuevaClaveSegura123",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        mensajes = [mensaje.message for mensaje in get_messages(response.wsgi_request)]
        self.assertIn("La clave actual es incorrecta.", mensajes)

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("ClaveVieja123"))
        self.assertFalse(self.usuario.check_password("NuevaClaveSegura123"))
