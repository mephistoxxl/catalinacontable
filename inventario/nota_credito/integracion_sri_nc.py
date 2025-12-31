"""
Integración con el SRI para Notas de Crédito Electrónicas
"""
import os
import logging
import tempfile
from datetime import datetime
from django.conf import settings

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
        # Nota: No usar `.path` porque storages tipo S3 no lo soportan.
        # Reutilizar el firmador oficial del proyecto (endesive) que lee PKCS#12 vía `.open()`.
        from inventario.sri.firmador_xades_sri import firmar_xml_xades_bes

        if not self.opciones.firma_electronica:
            raise ValueError("No hay firma electrónica configurada")
        if not self.opciones.password_firma:
            raise ValueError("No hay contraseña de firma configurada")

        xml_text = xml_content if isinstance(xml_content, str) else str(xml_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            xml_in = os.path.join(tmpdir, f"nc_{self.nc.id}_sin_firmar.xml")
            xml_out = os.path.join(tmpdir, f"nc_{self.nc.id}_firmado.xml")

            with open(xml_in, "w", encoding="utf-8") as f:
                f.write(xml_text)

            firmar_xml_xades_bes(xml_in, xml_out, empresa=self.empresa)

            with open(xml_out, "r", encoding="utf-8") as f:
                return f.read()
    
    def enviar_sri(self, xml_firmado):
        """Envía el XML firmado al SRI"""
        from inventario.sri.sri_client import SRIClient
        
        # Determinar ambiente
        ambiente = 'pruebas' if self.opciones.tipo_ambiente == '1' else 'produccion'
        
        cliente = SRIClient(ambiente=ambiente)

        # Envío + consulta autorización (con reintentos internos)
        clave_acceso = self.nc.clave_acceso
        xml_text = xml_firmado if isinstance(xml_firmado, str) else str(xml_firmado)
        return cliente.procesar_comprobante_completo(xml_text, clave_acceso)
    
    def procesar_respuesta(self, respuesta):
        """Procesa la respuesta del SRI y actualiza la NC"""

        def _extraer_autorizacion(respuesta_dict):
            try:
                autorizaciones = respuesta_dict.get('autorizaciones') or []
                if isinstance(autorizaciones, list) and autorizaciones:
                    return autorizaciones[0] or {}
            except Exception:
                return {}
            return {}

        def _formatear_mensajes(mensajes):
            lineas = []
            for m in (mensajes or []):
                tipo = (m.get('tipo') or '').strip()
                identificador = (m.get('identificador') or '').strip()
                mensaje = (m.get('mensaje') or '').strip()
                info = (m.get('informacionAdicional') or '').strip()

                # Si viene completamente vacío, ignorar (y caeremos a raw_response)
                if not any((tipo, identificador, mensaje, info)):
                    continue

                partes = []
                if tipo:
                    partes.append(tipo)
                if identificador:
                    partes.append(identificador)
                encabezado = ': '.join(partes) if partes else 'SRI'

                detalle = mensaje or '(sin mensaje)'
                if info:
                    detalle = f"{detalle} | {info}"

                lineas.append(f"{encabezado}: {detalle}")
            return '\n'.join(lineas).strip()

        estado_resp = respuesta.get('estado')

        if estado_resp == 'AUTORIZADO':
            self.nc.estado_sri = 'AUTORIZADO'
            aut0 = _extraer_autorizacion(respuesta)
            numero_aut = (
                respuesta.get('numeroAutorizacion')
                or aut0.get('numeroAutorizacion')
                or self.nc.clave_acceso
            )
            self.nc.numero_autorizacion = numero_aut

            fecha_aut = aut0.get('fechaAutorizacion') or respuesta.get('fechaAutorizacion')
            if fecha_aut:
                try:
                    # Manejar ISO con zona (Python 3.11+ lo soporta con fromisoformat)
                    self.nc.fecha_autorizacion = datetime.fromisoformat(str(fecha_aut).replace('Z', '+00:00'))
                except Exception:
                    self.nc.fecha_autorizacion = datetime.now()
            else:
                self.nc.fecha_autorizacion = datetime.now()
            self.nc.mensaje_sri = 'Autorizado correctamente'
            
            # Actualizar inventario si aplica
            self.nc.actualizar_inventario()
            
        elif estado_resp in ('RECHAZADO', 'NO AUTORIZADO'):
            self.nc.estado_sri = 'RECHAZADO'
            mensajes = respuesta.get('mensajes', [])
            raw = str(respuesta.get('raw_response') or respuesta)
            self.nc.mensaje_sri = _formatear_mensajes(mensajes) or raw[:2000]
        else:
            # Estados intermedios típicos: RECIBIDA / PENDIENTE / DEVUELTA / ERROR
            self.nc.estado_sri = estado_resp or 'ENVIADO'
            mensajes = respuesta.get('mensajes', [])
            raw = str(respuesta.get('raw_response') or respuesta)
            self.nc.mensaje_sri = _formatear_mensajes(mensajes) or raw[:2000]
        
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
