from django.core.management.base import BaseCommand
from django.db import transaction
from inventario.models import Usuario, Empresa, UsuarioEmpresa


class Command(BaseCommand):
    help = (
        "Repara relaciones Usuario-Empresa: puede limpiar, eliminar duplicados, "
        "y reconstruir vínculos ya sea por RUC (username=RUC) o vinculando todos a un RUC dado."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Solo reporta acciones sin modificar datos')
        parser.add_argument('--user', type=str, help='Limitar a un usuario (username)')
        parser.add_argument('--ruc', type=str, help='Limitar a una Empresa por RUC')
        parser.add_argument('--wipe', action='store_true', help='Eliminar vínculos UsuarioEmpresa en el alcance dado')
        parser.add_argument('--link-by-username-ruc', action='store_true', help='Crear vínculo si username de 13 dígitos coincide con Empresa.ruc')
        parser.add_argument('--create-missing-empresas-from-usernames', action='store_true', help='Crear Empresa faltante para usernames de 13 dígitos (RUC)')
        parser.add_argument('--link-all-to-ruc', type=str, help='Vincular todos los usuarios seleccionados al RUC indicado')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        user_filter = options.get('user')
        ruc_filter = options.get('ruc')
        do_wipe = options['wipe']
        link_by_username_ruc = options['link_by_username_ruc']
        create_missing_empresas = options['create_missing_empresas_from_usernames']
        link_all_to_ruc = options.get('link_all_to_ruc')

        usuarios_qs = Usuario.objects.all()
        if user_filter:
            usuarios_qs = usuarios_qs.filter(username=user_filter)
        empresas_scope = Empresa.objects.all()
        if ruc_filter:
            empresas_scope = empresas_scope.filter(ruc=ruc_filter)

        self.stdout.write(self.style.MIGRATE_HEADING('== Reparando relaciones Usuario-Empresa =='))
        self.stdout.write(f"Dry run: {dry_run}")

        with transaction.atomic():
            # 1) Limpiar vínculos inválidos u obvios duplicados
            invalid = UsuarioEmpresa.objects.exclude(usuario__in=usuarios_qs) | UsuarioEmpresa.objects.exclude(empresa__in=empresas_scope)
            inv_count = invalid.count()
            if inv_count:
                self.stdout.write(self.style.WARNING(f"Vínculos inválidos a eliminar: {inv_count}"))
                if not dry_run:
                    invalid.delete()

            # Duplicados (enforce unique_together)
            seen = set()
            dup_deleted = 0
            for link in UsuarioEmpresa.objects.select_related('usuario', 'empresa').order_by('usuario_id', 'empresa_id', 'id'):
                key = (link.usuario_id, link.empresa_id)
                if key in seen:
                    dup_deleted += 1
                    if not dry_run:
                        link.delete()
                else:
                    seen.add(key)
            if dup_deleted:
                self.stdout.write(self.style.WARNING(f"Duplicados eliminados: {dup_deleted}"))

            # 2) Wipe (opcional)
            if do_wipe:
                wipe_qs = UsuarioEmpresa.objects.all()
                if user_filter:
                    wipe_qs = wipe_qs.filter(usuario__username=user_filter)
                if ruc_filter:
                    wipe_qs = wipe_qs.filter(empresa__ruc=ruc_filter)
                wipe_count = wipe_qs.count()
                self.stdout.write(self.style.WARNING(f"Eliminando {wipe_count} vínculos en el alcance indicado"))
                if not dry_run:
                    wipe_qs.delete()

            # 3) Reconstrucción por reglas
            created = 0

            # 3a) Crear Empresas faltantes a partir de usernames con 13 dígitos
            if create_missing_empresas:
                created_empresas = 0
                for user in usuarios_qs:
                    uname = (user.username or '').strip()
                    if uname.isdigit() and len(uname) == 13:
                        if not Empresa.objects.filter(ruc=uname).exists():
                            if not dry_run:
                                Empresa.objects.create(ruc=uname, razon_social=f"Empresa {uname}")
                            created_empresas += 1
                if created_empresas:
                    self.stdout.write(self.style.SUCCESS(f"Empresas creadas: {created_empresas}"))

            # 3b) Vincular por username == RUC (13 dígitos)
            if link_by_username_ruc:
                for user in usuarios_qs:
                    uname = user.username.strip()
                    if uname.isdigit() and len(uname) == 13:
                        try:
                            emp = Empresa.objects.get(ruc=uname)
                        except Empresa.DoesNotExist:
                            continue
                        if not UsuarioEmpresa.objects.filter(usuario=user, empresa=emp).exists():
                            if not dry_run:
                                UsuarioEmpresa.objects.create(usuario=user, empresa=emp)
                            created += 1

            # 3c) Vincular todos los usuarios seleccionados a un RUC dado
            if link_all_to_ruc:
                try:
                    target_emp = Empresa.objects.get(ruc=link_all_to_ruc)
                except Empresa.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Empresa con RUC {link_all_to_ruc} no existe"))
                else:
                    for user in usuarios_qs:
                        if not UsuarioEmpresa.objects.filter(usuario=user, empresa=target_emp).exists():
                            if not dry_run:
                                UsuarioEmpresa.objects.create(usuario=user, empresa=target_emp)
                            created += 1

            self.stdout.write(self.style.SUCCESS(f"Vínculos creados: {created}"))

        self.stdout.write(self.style.SUCCESS('Listo. Relaciones consistentes.'))
