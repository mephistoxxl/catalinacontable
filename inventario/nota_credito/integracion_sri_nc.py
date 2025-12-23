"""
Integración con el SRI para Notas de Crédito Electrónicas
"""
import os
import logging
from datetime import datetime
from django.conf import settings

from inventario.sri.integracion_django import IntegracionSRI
from inventario.models import Opciones
from .models import NotaCredito
from .xml_generator_nc import XMLGeneratorNotaCredito

logger = logging.getLogger(__name__)


class IntegracionSRINotaCredito:
    """
    Maneja la integración con el SRI para Notas de Crédito
    """
    
    def __init__(self, nota_credito):
        """
        Args:
            nota_credito: Instancia de NotaCredito
        """
        self.nc = nota_credito
        self.empresa = nota_credito.empresa
        self.opciones = Opciones.objects.for_tenant(self.empresa).first()
        
        if not self.opciones:
            raise ValueError("No se encontró configuración de opciones para la empresa")
    
    def generar_xml(self):
        """Genera el XML de la Nota de Crédito"""
        generator = XMLGeneratorNotaCredito(self.nc, self.opciones)
        
        # Generar clave de acceso si no existe
        if not self.nc.clave_acceso:
            self.nc.clave_acceso = generator.generar_clave_acceso()
            self.nc.save(update_fields=['clave_acceso'])
        
        xml_content = generator.generar_xml()
        return xml_content
    
    def firmar_xml(self, xml_content):
        """Firma el XML con la firma electrónica"""
        from inventario.sri.firmador_xades import firmar_xml_xades_bes
        
        # Obtener ruta de la firma y contraseña
        if not self.opciones.firma_electronica:
            raise ValueError("No hay firma electrónica configurada")
        
        firma_path = self.opciones.firma_electronica.path
        password = self.opciones.password_firma
        
        if not password:
            raise ValueError("No hay contraseña de firma configurada")
        
        # Firmar
        xml_firmado = firmar_xml_xades_bes(xml_content, firma_path, password)
        return xml_firmado
    
    def enviar_sri(self, xml_firmado):
        """Envía el XML firmado al SRI"""
        from inventario.sri.cliente_sri import ClienteSRI
        
        # Determinar ambiente
        ambiente = 'pruebas' if self.opciones.tipo_ambiente == '1' else 'produccion'
        
        cliente = ClienteSRI(ambiente=ambiente)
        
        # Enviar al SRI
        respuesta_recepcion = cliente.enviar_comprobante(xml_firmado)
        
        if respuesta_recepcion.get('estado') == 'RECIBIDA':
            # Autorizar
            clave_acceso = self.nc.clave_acceso
            respuesta_autorizacion = cliente.autorizar_comprobante(clave_acceso)
            
            return respuesta_autorizacion
        else:
            return respuesta_recepcion
    
    def procesar_respuesta(self, respuesta):
        """Procesa la respuesta del SRI y actualiza la NC"""
        
        if respuesta.get('estado') == 'AUTORIZADO':
            self.nc.estado_sri = 'AUTORIZADO'
            self.nc.numero_autorizacion = respuesta.get('numeroAutorizacion', self.nc.clave_acceso)
            self.nc.fecha_autorizacion = datetime.now()
            self.nc.mensaje_sri = 'Autorizado correctamente'
            
            # Actualizar inventario si aplica
            self.nc.actualizar_inventario()
            
        elif respuesta.get('estado') == 'RECHAZADO':
            self.nc.estado_sri = 'RECHAZADO'
            mensajes = respuesta.get('mensajes', [])
            self.nc.mensaje_sri = '\n'.join([
                f"{m.get('tipo', '')}: {m.get('mensaje', '')}"
                for m in mensajes
            ])
        else:
            self.nc.estado_sri = 'ENVIADO'
            self.nc.mensaje_sri = str(respuesta)
        
        self.nc.save()
        return self.nc.estado_sri
    
    def procesar_completo(self):
        """
        Ejecuta el proceso completo:
        1. Generar XML
        2. Firmar
        3. Enviar al SRI
        4. Procesar respuesta
        """
        try:
            logger.info(f"Iniciando proceso de NC {self.nc.numero_completo}")
            
            # 1. Generar XML
            xml_content = self.generar_xml()
            logger.info("XML generado correctamente")
            
            # 2. Firmar
            xml_firmado = self.firmar_xml(xml_content)
            logger.info("XML firmado correctamente")
            
            # 3. Enviar al SRI
            respuesta = self.enviar_sri(xml_firmado)
            logger.info(f"Respuesta SRI: {respuesta}")
            
            # 4. Procesar respuesta
            estado = self.procesar_respuesta(respuesta)
            logger.info(f"Estado final: {estado}")
            
            return {
                'success': estado == 'AUTORIZADO',
                'estado': estado,
                'mensaje': self.nc.mensaje_sri,
                'clave_acceso': self.nc.clave_acceso,
                'numero_autorizacion': self.nc.numero_autorizacion
            }
            
        except Exception as e:
            logger.exception(f"Error procesando NC {self.nc.numero_completo}")
            self.nc.estado_sri = 'RECHAZADO'
            self.nc.mensaje_sri = str(e)
            self.nc.save()
            
            return {
                'success': False,
                'estado': 'ERROR',
                'mensaje': str(e)
            }
    
    def guardar_xml(self, xml_content, tipo='generado'):
        """
        Guarda el XML en el sistema de archivos
        Args:
            xml_content: Contenido del XML
            tipo: 'generado', 'firmado', o 'autorizado'
        """
        # Crear directorio si no existe
        directorio = os.path.join(
            settings.MEDIA_ROOT,
            'notas_credito_xml',
            str(self.empresa.id)
        )
        os.makedirs(directorio, exist_ok=True)
        
        # Nombre del archivo
        nombre_archivo = f"nc_{self.nc.numero_completo.replace('-', '_')}_{tipo}.xml"
        ruta_completa = os.path.join(directorio, nombre_archivo)
        
        # Guardar
        with open(ruta_completa, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        logger.info(f"XML guardado en: {ruta_completa}")
        return ruta_completa
