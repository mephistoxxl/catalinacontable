from django.core.management.base import BaseCommand

from inventario.models import Empresa, Opciones


class Command(BaseCommand):
    help = (
        "Asigna el campo empresa en Opciones buscando la Empresa cuyo RUC coincide"
        " con el identificacion registrado."
    )

    def handle(self, *args, **options):
        asignadas = 0
        for opcion in Opciones.objects.all():
            if opcion.empresa_id:
                continue
            empresa = Empresa.objects.filter(ruc=opcion.identificacion).first()
            if empresa:
                opcion.empresa = empresa
                opcion.save(update_fields=["empresa"])
                asignadas += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Opciones {opcion.id} vinculada a Empresa {empresa.ruc}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"No se encontró Empresa para Opciones {opcion.id} con RUC {opcion.identificacion}"
                    )
                )
        self.stdout.write(self.style.NOTICE(f"Asignaciones realizadas: {asignadas}"))

