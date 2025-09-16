from django.core.management.base import BaseCommand
from inventario.models import Empresa, Opciones

class Command(BaseCommand):
    help = "Muestra diagnostico de firmas electrónicas por empresa y crea registros faltantes opcionalmente"

    def add_arguments(self, parser):
        parser.add_argument('--crear-faltantes', action='store_true', help='Crear registros Opciones faltantes con datos mínimos')

    def handle(self, *args, **options):
        crear = options.get('crear_faltantes')
        empresas = Empresa.objects.all().order_by('id')
        self.stdout.write(f"Empresas encontradas: {empresas.count()}")
        for e in empresas:
            op = Opciones.objects.filter(empresa=e).first()
            if not op and crear:
                # Proveer campos mínimos requeridos por validaciones
                op = Opciones(
                    empresa=e,
                    identificacion=e.ruc,
                    razon_social=getattr(e, 'razon_social', f'EMPRESA {e.id}'),
                    direccion_establecimiento='[PENDIENTE DIRECCIÓN]',
                    correo='pendiente@empresa.com',
                    telefono='0000000000'
                )
                try:
                    op.save()
                    self.stdout.write(self.style.WARNING(f"[CREADO] Opciones básico para empresa {e.id} {e.ruc}"))
                except Exception as ex:
                    self.stdout.write(self.style.ERROR(f"Error creando Opciones para empresa {e.id}: {ex}"))
            if op:
                self.stdout.write(f"Empresa {e.id} {e.ruc}: firma={'SI' if op.firma_electronica else 'NO'} password={'SI' if op.password_firma else 'NO'} caducidad={op.fecha_caducidad_firma}")
            else:
                self.stdout.write(self.style.ERROR(f"Empresa {e.id} {e.ruc}: SIN REGISTRO OPCIONES"))
        # Contenido global
        total_con_firma = Opciones.objects.filter(firma_electronica__isnull=False, password_firma__isnull=False).count()
        self.stdout.write(f"Total firmas configuradas completas: {total_con_firma}")
