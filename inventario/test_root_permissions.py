from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from .models import Empresa, Usuario


class RootUserManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.root = get_user_model().objects.create_user(
            username='root',
            email='root@example.com',
            password='pass',
            is_superuser=True,
            is_staff=True,
            nivel=Usuario.ROOT,
        )
        self.client.force_login(self.root)

    def test_root_can_manage_users_across_empresas(self):
        empresa1 = Empresa.objects.create(ruc='1234567890123', razon_social='Empresa1')
        empresa2 = Empresa.objects.create(ruc='9876543210987', razon_social='Empresa2')

        session = self.client.session
        session['empresa_activa'] = empresa1.id
        session.save()
        resp = self.client.post('/inventario/crearUsuario', {
            'identificacion': '1111111111111',
            'nombre_completo': 'Admin Uno',
            'email': 'admin1@example.com',
            'password': 'pass123',
            'rep_password': 'pass123',
            'level': Usuario.ADMIN,
        })
        self.assertEqual(resp.status_code, 302)
        admin1 = Usuario.objects.get(username='1111111111111')
        self.assertEqual(admin1.nivel, Usuario.ADMIN)
        self.assertTrue(admin1.empresas.filter(id=empresa1.id).exists())

        session = self.client.session
        session['empresa_activa'] = empresa2.id
        session.save()
        resp = self.client.post('/inventario/crearUsuario', {
            'identificacion': '2222222222222',
            'nombre_completo': 'User Dos',
            'email': 'user2@example.com',
            'password': 'pass123',
            'rep_password': 'pass123',
            'level': Usuario.USER,
        })
        self.assertEqual(resp.status_code, 302)
        user2 = Usuario.objects.get(username='2222222222222')
        self.assertEqual(user2.nivel, Usuario.USER)
        self.assertTrue(user2.empresas.filter(id=empresa2.id).exists())
