from django.apps import AppConfig
from django.db.models.signals import post_migrate


class InventarioConfig(AppConfig):
    name = 'inventario'

    def ready(self):
        from django.contrib.auth.models import Group, Permission

        def create_default_groups(sender, **kwargs):
            admin_group, _ = Group.objects.get_or_create(name='Administrador')
            user_group, _ = Group.objects.get_or_create(name='Usuario')
            admin_group.permissions.set(Permission.objects.all())

        post_migrate.connect(create_default_groups, sender=self)
