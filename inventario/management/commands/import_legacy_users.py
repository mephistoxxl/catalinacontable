from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_datetime
import json
import os


class Command(BaseCommand):
    help = "Importa usuarios históricos y sus vínculos Empresa desde backup_sqlite_data.json sin tocar otros modelos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            dest="file",
            default="backup_sqlite_data.json",
            help="Ruta al archivo JSON de backup (default: backup_sqlite_data.json)",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Si se especifica, actualiza email/flags de usuarios existentes (no cambia password)",
        )

    def handle(self, *args, **options):
        from inventario.models import Usuario, Empresa, UsuarioEmpresa

        backup_path = options["file"]

        if not os.path.exists(backup_path):
            self.stderr.write(self.style.ERROR(f"No existe el archivo: {backup_path}"))
            return

        with open(backup_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Agrupar por modelo
        by_model = {}
        for item in data:
            by_model.setdefault(item["model"], []).append(item)

        # Construir mapa de empresas del backup: old_pk -> {ruc, razon_social}
        empresa_map = {}
        for item in by_model.get("inventario.empresa", []):
            old_pk = item.get("pk")
            fields = item.get("fields", {})
            ruc = fields.get("ruc")
            if old_pk and ruc:
                empresa_map[old_pk] = {"ruc": ruc, "razon_social": fields.get("razon_social")}

        created_users = 0
        updated_users = 0
        created_links = 0

        with transaction.atomic():
            # 1) Importar usuarios
            for item in by_model.get("inventario.usuario", []):
                fields = dict(item.get("fields", {}))

                username = fields.get("username")
                email = fields.get("email")
                if not username:
                    continue

                # Campos básicos
                defaults = {
                    "email": email or f"{username}@example.com",
                    "first_name": fields.get("first_name") or "",
                    "last_name": fields.get("last_name") or "",
                    "is_superuser": bool(fields.get("is_superuser", False)),
                    "is_staff": bool(fields.get("is_staff", False)),
                    "is_active": bool(fields.get("is_active", True)),
                    "nivel": fields.get("nivel"),
                }

                user, created = Usuario.objects.get_or_create(username=username, defaults=defaults)

                # Si es nuevo, establecer password pre-hasheado y fechas
                if created:
                    # Asignar password tal cual (hash ya viene del backup)
                    raw_hash = fields.get("password")
                    if raw_hash:
                        user.password = raw_hash
                    # Fechas (opcional)
                    dj = fields.get("date_joined")
                    if dj:
                        dt = parse_datetime(dj)
                        if dt:
                            user.date_joined = dt
                    ll = fields.get("last_login")
                    if ll:
                        dt = parse_datetime(ll)
                        if dt:
                            user.last_login = dt
                    user.save()
                    created_users += 1
                    self.stdout.write(self.style.SUCCESS(f"+ Usuario creado: {username}"))
                else:
                    # No sobreescribir admin sembrado por defecto a menos que lo pidan expresamente
                    if options["update_existing"]:
                        changed = False
                        for k, v in defaults.items():
                            if getattr(user, k) != v and k != "email":
                                setattr(user, k, v)
                                changed = True
                        # email es único; solo actualizar si no colisiona o es igual
                        if email and user.email != email:
                            # Verificar colisión
                            if not Usuario.objects.filter(email=email).exclude(id=user.id).exists():
                                user.email = email
                                changed = True
                        if changed:
                            user.save()
                            updated_users += 1
                            self.stdout.write(self.style.WARNING(f"~ Usuario actualizado: {username}"))
                    else:
                        self.stdout.write(f"= Usuario existente (sin cambios): {username}")

            # 2) Crear vínculos Usuario-Empresa del backup
            for item in by_model.get("inventario.usuarioempresa", []):
                fields = item.get("fields", {})

                # El backup usa natural key para usuario: lista con username
                usuario_key = fields.get("usuario")
                if isinstance(usuario_key, list) and usuario_key:
                    username = usuario_key[0]
                else:
                    # No compatible
                    continue

                old_empresa_pk = fields.get("empresa")
                if old_empresa_pk not in empresa_map:
                    # Sin mapeo, vincular a la primera Empresa existente (fallback)
                    empresa = Empresa.objects.first()
                else:
                    # Obtener/crear empresa por RUC para evitar conflictos de PK
                    ruc = empresa_map[old_empresa_pk]["ruc"]
                    razon = empresa_map[old_empresa_pk].get("razon_social") or ruc
                    empresa, _ = Empresa.objects.get_or_create(ruc=ruc, defaults={"razon_social": razon})

                try:
                    usuario = Usuario.objects.get(username=username)
                except Usuario.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"! Usuario no encontrado para vínculo: {username}"))
                    continue

                _, created_link = UsuarioEmpresa.objects.get_or_create(usuario=usuario, empresa=empresa)
                if created_link:
                    created_links += 1

        # Resumen
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Resumen de importación de usuarios ==="))
        self.stdout.write(self.style.SUCCESS(f"Usuarios creados: {created_users}"))
        self.stdout.write(self.style.WARNING(f"Usuarios actualizados: {updated_users}"))
        self.stdout.write(self.style.SUCCESS(f"Vínculos Usuario-Empresa creados: {created_links}"))
