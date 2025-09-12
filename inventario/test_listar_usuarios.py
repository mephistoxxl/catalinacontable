from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Empresa


class ListarUsuariosViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.empresa1 = Empresa.objects.create(ruc="1234567890123", razon_social="Empresa1")
        self.empresa2 = Empresa.objects.create(ruc="9876543210987", razon_social="Empresa2")

        self.superuser = User.objects.create_superuser(
            username="super", email="super@example.com", password="pass"
        )
        self.superuser.empresas.add(self.empresa1)

        self.user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="pass"
        )
        self.user1.empresas.add(self.empresa1)

        self.user1b = User.objects.create_user(
            username="user1b", email="user1b@example.com", password="pass"
        )
        self.user1b.empresas.add(self.empresa1)

        self.user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="pass"
        )
        self.user2.empresas.add(self.empresa2)

    def test_company_user_sees_only_company_users_without_admins(self):
        self.client.force_login(self.user1)
        session = self.client.session
        session['empresa_activa'] = self.empresa1.id
        session.save()

        response = self.client.get(reverse('inventario:listarUsuarios'))
        self.assertEqual(response.status_code, 200)
        tabla = list(response.context['tabla'])
        self.assertIn(self.user1, tabla)
        self.assertIn(self.user1b, tabla)
        self.assertNotIn(self.user2, tabla)
        self.assertNotIn(self.superuser, tabla)
