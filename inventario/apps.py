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

        # Importar modelos de liquidación de compra cuando la app ya está lista
        # para evitar conflictos con la facturación existente y con el registro
        # anticipado de logging.
        from .liquidacion_compra import models as _liquidacion_models  # noqa: F401
        
        # Importar modelos de notas de crédito
        from .nota_credito import models as _nota_credito_models  # noqa: F401
