import logging
from django.core.management.base import BaseCommand
from inventario.sri.integracion_django import SRIIntegration
from inventario.models import Factura

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Procesar facturas electrónicas con el SRI'

    def add_arguments(self, parser):
        parser.add_argument(
            '--factura-id',
            type=int,
            help='ID de la factura específica a procesar'
        )
        parser.add_argument(
            '--estado',
            choices=['PENDIENTE', 'RECHAZADO', 'ERROR'],
            help='Procesar todas las facturas con este estado'
        )
        parser.add_argument(
            '--consultar',
            action='store_true',
            help='Solo consultar estado sin reenviar'
        )
        parser.add_argument(
            '--diagnostico',
            action='store_true',
            help='Verificar disponibilidad de servicios SRI'
        )

    def handle(self, *args, **options):
        # Diagnóstico de servicios
        if options['diagnostico']:
            self.diagnosticar_servicios()
            return

        # Procesar factura específica
        if options['factura_id']:
            self.procesar_factura_especifica(options['factura_id'], options['consultar'])
            return

        # Procesar por estado
        if options['estado']:
            self.procesar_facturas_por_estado(options['estado'], options['consultar'])
            return

        # Si no se especifica, procesar todas las pendientes
        self.procesar_facturas_pendientes(options['consultar'])

    def diagnosticar_servicios(self):
        """Verificar disponibilidad de servicios SRI"""
        self.stdout.write(self.style.SUCCESS('=== DIAGNÓSTICO SRI ==='))
        
        try:
            empresa = Factura.all_objects.first().empresa if Factura.all_objects.exists() else None
            integration = SRIIntegration(empresa=empresa)
            estado = integration.cliente.verificar_servicio()

            self.stdout.write(f"Ambiente: {integration.ambiente}")
            self.stdout.write(f"Servicio Recepción: {'✅ Disponible' if estado['recepcion']['disponible'] else '❌ No disponible'}")
            self.stdout.write(f"Servicio Autorización: {'✅ Disponible' if estado['autorizacion']['disponible'] else '❌ No disponible'}")
            
            if estado['recepcion']['error']:
                self.stdout.write(self.style.ERROR(f"Error Recepción: {estado['recepcion']['error']}"))
            if estado['autorizacion']['error']:
                self.stdout.write(self.style.ERROR(f"Error Autorización: {estado['autorizacion']['error']}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error en diagnóstico: {e}"))

    def procesar_factura_especifica(self, factura_id, solo_consultar=False):
        """Procesar una factura específica"""
        try:
            factura = Factura.all_objects.get(id=factura_id)
            self.stdout.write(f"Procesando factura: {factura.numero_factura}")

            integration = SRIIntegration(empresa=factura.empresa)
            
            if solo_consultar:
                resultado = integration.consultar_estado_factura(factura_id)
            else:
                resultado = integration.procesar_factura(factura_id)
            
            self.mostrar_resultado(resultado, factura)
            
        except Factura.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Factura con ID {factura_id} no encontrada"))

    def procesar_facturas_por_estado(self, estado, solo_consultar=False):
        """Procesar todas las facturas con un estado específico"""
        facturas = Factura.all_objects.filter(estado=estado)
        
        if not facturas.exists():
            self.stdout.write(f"No hay facturas con estado {estado}")
            return
            
        self.stdout.write(f"Procesando {facturas.count()} facturas con estado {estado}")

        for factura in facturas:
            self.stdout.write(f"  - {factura.numero_factura}...")

            try:
                integration = SRIIntegration(empresa=factura.empresa)
                if solo_consultar:
                    resultado = integration.consultar_estado_factura(factura.id)
                else:
                    resultado = integration.procesar_factura(factura.id)
                
                self.mostrar_resultado(resultado, factura, indent="    ")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    Error: {e}"))

    def procesar_facturas_pendientes(self, solo_consultar=False):
        """Procesar todas las facturas pendientes"""
        facturas = Factura.all_objects.filter(estado__in=['PENDIENTE', 'RECIBIDA'])
        
        if not facturas.exists():
            self.stdout.write("No hay facturas pendientes")
            return
            
        self.stdout.write(f"Procesando {facturas.count()} facturas pendientes")

        exitosas = 0
        errores = 0

        for factura in facturas:
            self.stdout.write(f"  - {factura.numero_factura}...")

            try:
                integration = SRIIntegration(empresa=factura.empresa)
                if solo_consultar:
                    resultado = integration.consultar_estado_factura(factura.id)
                else:
                    resultado = integration.procesar_factura(factura.id)
                
                if resultado['success']:
                    exitosas += 1
                else:
                    errores += 1
                
                self.mostrar_resultado(resultado, factura, indent="    ")
                
            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(f"    Error: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"\nResultados: {exitosas} exitosas, {errores} errores"))

    def mostrar_resultado(self, resultado, factura, indent=""):
        """Mostrar resultado formateado"""
        if resultado['success']:
            estado = resultado['resultado']['estado']
            
            if estado == 'AUTORIZADO':
                self.stdout.write(self.style.SUCCESS(f"{indent}✅ AUTORIZADO"))
                if 'autorizaciones' in resultado['resultado']:
                    aut = resultado['resultado']['autorizaciones'][0]
                    self.stdout.write(f"{indent}   Número: {aut['numeroAutorizacion']}")
                    self.stdout.write(f"{indent}   Fecha: {aut['fechaAutorizacion']}")
                    
            elif estado == 'NO AUTORIZADO':
                self.stdout.write(self.style.ERROR(f"{indent}❌ NO AUTORIZADO"))
                
            elif estado == 'RECIBIDA':
                self.stdout.write(self.style.WARNING(f"{indent}⏳ RECIBIDA"))
                
            else:
                self.stdout.write(self.style.WARNING(f"{indent}⚠️ {estado}"))
                
            # Mostrar mensajes
            if 'resultado' in resultado and resultado['resultado'].get('mensajes'):
                for msg in resultado['resultado']['mensajes']:
                    self.stdout.write(f"{indent}   {msg['tipo']}: {msg['mensaje']}")
                    
        else:
            self.stdout.write(self.style.ERROR(f"{indent}❌ Error: {resultado['message']}"))