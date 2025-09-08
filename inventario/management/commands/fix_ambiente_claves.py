import sys
from django.core.management.base import BaseCommand
from django.db import transaction

from inventario.models import Factura
from inventario.sri.ambiente import obtener_ambiente_sri
from inventario.sri.integracion_django import SRIIntegration


class Command(BaseCommand):
    help = (
        "Detecta facturas con desajuste entre el dígito de ambiente en la clave de acceso "
        "y el ambiente configurado, permite limpiar la clave para su regeneración y, opcionalmente, "
        "regenerar el XML (validando XSD)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar lo que se haría, sin modificar nada",
        )
        parser.add_argument(
            "--regen-xml",
            action="store_true",
            help="Tras limpiar la clave, intentar generar XML validado para la factura",
        )
        parser.add_argument(
            "--only",
            type=int,
            help="ID de factura específica a procesar (opcional)",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        regen_xml = options.get("regen_xml", False)
        only = options.get("only")

        qs = Factura.objects.all()
        if only:
            qs = qs.filter(id=only)
        else:
            # Evitar tocar facturas ya autorizadas
            qs = qs.exclude(estado_sri__in=["AUTORIZADA", "AUTORIZADO"]).exclude(clave_acceso__isnull=True).exclude(clave_acceso="")

        total = qs.count()
        if total == 0:
            self.stdout.write("No hay facturas candidatas.")
            return

        ambiente_actual = obtener_ambiente_sri(qs.first().empresa if total else None)
        self.stdout.write(self.style.NOTICE(f"Ambiente actual: {ambiente_actual} ({'PRUEBAS' if ambiente_actual=='1' else 'PRODUCCIÓN'})"))

        self.stdout.write(f"Facturas a revisar: {total}")

        afectados = 0
        corregidos = 0
        errores = 0

        for factura in qs.iterator():
            ambiente = obtener_ambiente_sri(factura.empresa)
            clave = getattr(factura, "clave_acceso", None)
            if not clave or len(clave) < 24:
                continue
            clave_amb = clave[23]
            if clave_amb != ambiente:
                afectados += 1
                self.stdout.write(self.style.WARNING(
                    f"Factura {factura.id} con clave {clave} → dígito ambiente={clave_amb} != {ambiente}"
                ))
                if dry_run:
                    continue

                try:
                    with transaction.atomic():
                        factura.clave_acceso = None
                        factura.save(update_fields=["clave_acceso"])
                    corregidos += 1
                    self.stdout.write(self.style.SUCCESS(f"✔ Clave limpiada para factura {factura.id}"))

                    if regen_xml:
                        try:
                            integration = SRIIntegration(empresa=factura.empresa)
                            xml_path = integration.generar_xml_factura(factura, validar_xsd=True)
                            self.stdout.write(self.style.SUCCESS(f"  ↳ XML regenerado y validado: {xml_path}"))
                        except Exception as e:
                            errores += 1
                            self.stderr.write(self.style.ERROR(f"  ↳ Error al regenerar XML: {e}"))

                except Exception as e:
                    errores += 1
                    self.stderr.write(self.style.ERROR(f"✖ Error corrigiendo factura {factura.id}: {e}"))

        self.stdout.write("")
        self.stdout.write("Resumen:")
        self.stdout.write(f"  Detectadas con desajuste: {afectados}")
        self.stdout.write(f"  Corregidas (clave limpiada): {corregidos}{' (dry-run)' if dry_run else ''}")
        self.stdout.write(f"  Errores: {errores}")
