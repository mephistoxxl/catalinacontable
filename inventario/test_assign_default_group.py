from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase


class AssignDefaultGroupTests(TestCase):
    def test_user_group_updates_when_becomes_superuser(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="user", email="user@example.com", password="pass"
        )
        usuario_group = Group.objects.get(name="Usuario")
        self.assertIn(usuario_group, user.groups.all())

        user.is_superuser = True
        user.save()
        user.refresh_from_db()
        admin_group = Group.objects.get(name="Administrador")
        self.assertIn(admin_group, user.groups.all())
        self.assertNotIn(usuario_group, user.groups.all())

    def test_user_group_updates_when_loses_superuser(self):
        User = get_user_model()
        user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pass"
        )
        admin_group = Group.objects.get(name="Administrador")
        self.assertIn(admin_group, user.groups.all())

        user.is_superuser = False
        user.save()
        user.refresh_from_db()
        usuario_group = Group.objects.get(name="Usuario")
        self.assertIn(usuario_group, user.groups.all())
        self.assertNotIn(admin_group, user.groups.all())
