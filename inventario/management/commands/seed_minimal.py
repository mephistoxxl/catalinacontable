from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Seed minimal initial data: Empresa, Opciones, Secuencias, Admin, Almacén, Caja, Facturador"

    def handle(self, *args, **options):
        # Lazy imports to avoid issues if models change
        from inventario.models import (
            Empresa,
            Opciones,
            Secuencia,
            Usuario,
            UsuarioEmpresa,
            Almacen,
            Caja,
            Facturador,
        )

        with transaction.atomic():
            # Empresa demo
            empresa, created_empresa = Empresa.objects.get_or_create(
                ruc="1790012345001",
                defaults={
                    "razon_social": "EMPRESA DEMO S.A.",
                    "tipo_ambiente": "1",
                },
            )

            # Opciones vinculadas a empresa
            opciones, created_opc = Opciones.objects.get_or_create(
                empresa=empresa,
                defaults={
                    "identificacion": empresa.ruc,
                    "razon_social": "EMPRESA DEMO S.A.",
                    "nombre_comercial": "EMPRESA DEMO",
                    "direccion_establecimiento": "AV. DEMO Y CALLE FALSA 123",
                    "correo": "demo@empresa.com",
                    "telefono": "0990000000",
                    # valores por defecto ya cubren: tipo_ambiente="1"
                },
            )

            # Secuencias: Factura (01) y Guía de Remisión (06)
            Secuencia.objects.get_or_create(
                empresa=empresa,
                tipo_documento="01",
                establecimiento=1,
                punto_emision=1,
                defaults={
                    "descripcion": "FACTURA",
                    "secuencial": 1,
                    "activo": True,
                    "iva": True,
                    "fiscal": True,
                    "documento_electronico": True,
                },
            )
            Secuencia.objects.get_or_create(
                empresa=empresa,
                tipo_documento="06",
                establecimiento=1,
                punto_emision=1,
                defaults={
                    "descripcion": "GUIA DE REMISION",
                    "secuencial": 1,
                    "activo": True,
                    "iva": False,
                    "fiscal": True,
                    "documento_electronico": True,
                },
            )

            # Usuario admin
            admin_user, created_admin = Usuario.objects.get_or_create(
                username="admin",
                defaults={
                    "email": "admin@example.com",
                    "first_name": "Admin",
                    "last_name": "Demo",
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            if created_admin:
                admin_user.set_password("admin123")
                admin_user.save()

            # Relación Usuario-Empresa
            UsuarioEmpresa.objects.get_or_create(usuario=admin_user, empresa=empresa)

            # Almacén principal
            almacen, _ = Almacen.objects.get_or_create(
                empresa=empresa, descripcion="Almacén Principal", defaults={"activo": True}
            )

            # Caja
            caja, created_caja = Caja.objects.get_or_create(
                empresa=empresa,
                descripcion="Caja Ventas",
                defaults={
                    "activo": True,
                    "creado_por": admin_user,
                },
            )

            # Facturador demo
            try:
                facturador, created_fact = Facturador.objects.get_or_create(
                    empresa=empresa,
                    correo="demo@empresa.com",
                    defaults={
                        "nombres": "Facturador Demo",
                        "telefono": "0991111111",
                        "activo": True,
                        "descuento_permitido": 10.00,
                    },
                )
                if created_fact:
                    facturador.set_password("demo123")
                    facturador.save()
            except Exception:
                # En caso de particularidades del modelo Facturador, continuar sin bloquear el seed
                pass

        self.stdout.write(self.style.SUCCESS("Seed minimal realizado."))
