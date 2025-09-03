from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from django.db import transaction, connection
from inventario.models import Factura, Cliente, Empresa


class Command(BaseCommand):
    help = (
        "Repara claves foráneas inválidas en Factura.cliente: "
        "si cliente_id no corresponde a un Cliente.id, intenta mapear por identificacion_cliente "
        "(y empresa) y opcionalmente crea el Cliente faltante."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='No guarda cambios, solo reporta')
        parser.add_argument('--only', type=int, help='Procesa solo la factura con este ID')
        parser.add_argument('--create-missing', action='store_true', help='Crea Cliente si no existe')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        only = options.get('only')
        create_missing = options.get('create_missing')

        # Detectar facturas con cliente_id inválido
        cliente_exist = Cliente.objects.filter(id=OuterRef('cliente_id'))
        base_qs = Factura.objects.filter(cliente_id__isnull=False).annotate(has_cliente=Exists(cliente_exist)).filter(has_cliente=False)
        if only:
            base_qs = base_qs.filter(id=only)

        total = base_qs.count()
        self.stdout.write(self.style.WARNING(f"Facturas con FK cliente inválida: {total}"))
    fixed = 0
        created_clients = 0
        unresolved = 0

        def guess_tipo_identificacion(ident):
            ident = (ident or '').strip()
            if len(ident) == 13:
                return '04'  # RUC
            if len(ident) == 10:
                return '05'  # Cédula
            return '07'      # Consumidor Final / Otros

    def process_factura(f):
            nonlocal fixed, created_clients, unresolved
            ident = (f.identificacion_cliente or '').strip()

            # 1) Buscar por empresa + identificacion_cliente
            cli = None
            if f.empresa_id and ident:
                cli = Cliente.objects.filter(empresa_id=f.empresa_id, identificacion=ident).first()

            # 2) Fallback: algunos datos viejos guardaron identificacion en cliente_id
            if cli is None and f.empresa_id and f.cliente_id:
                cli = Cliente.objects.filter(empresa_id=f.empresa_id, identificacion=str(f.cliente_id)).first()

            # 3) Crear si se permite y hay datos mínimos
            if cli is None and create_missing and f.empresa_id and ident:
                cli = Cliente.objects.create(
                    empresa_id=f.empresa_id,
                    tipoIdentificacion=guess_tipo_identificacion(ident),
                    identificacion=ident,
                    razon_social=f.nombre_cliente or f"CLIENTE {ident}",
                    nombre_comercial=None,
                    direccion='S/D',
                    telefono='',
                    correo=f"sin-correo-{ident}@local.test",
                    observaciones='',
                    convencional='',
                    tipoVenta='1',
                    tipoRegimen='1',
                    tipoCliente='1',
                )
                created_clients += 1

            if cli is None:
                unresolved += 1
                self.stdout.write(self.style.ERROR(
                    f"No se pudo resolver Factura {f.id} (empresa={f.empresa_id}, ident='{ident}', cliente_id={f.cliente_id})"
                ))
                return

            if dry_run:
                self.stdout.write(f"→ Factura {f.id}: set cliente_id {f.cliente_id} → {cli.id} ({cli.identificacion})")
            else:
                Factura.objects.filter(id=f.id).update(cliente_id=cli.id)
            fixed += 1

        if dry_run:
            for f in base_qs.iterator():
                process_factura(f)
        else:
            # Do updates with constraints disabled to avoid interim FK failures
            with transaction.atomic():
                with connection.constraint_checks_disabled():
                    for f in base_qs.iterator():
                        process_factura(f)
                # Re-validate all constraints at the end
                connection.check_constraints()

        summary = (
            f"Arregladas: {fixed} | Clientes creados: {created_clients} | Sin resolver: {unresolved}"
        )
        if dry_run:
            self.stdout.write(self.style.NOTICE(f"[DRY-RUN] {summary}"))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
