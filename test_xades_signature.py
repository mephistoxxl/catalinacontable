#!/usr/bin/env python
"""
Test para verificar la validez de la firma XAdES-BES
Este script prueba la generación de SignatureValue con padding PKCS#1 v1.5
"""

import os
import sys
import tempfile
import logging
from lxml import etree

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Importar el firmador
try:
    from inventario.sri.firmador_xades import SRIXAdESFirmador, XAdESError
    from inventario.models import Opciones
    from django.conf import settings
    import django
    
    # Configurar Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
    django.setup()
    
except ImportError as e:
    logger.error(f"Error al importar módulos: {e}")
    sys.exit(1)

def crear_xml_prueba():
    """Crear un XML de prueba válido para firmar"""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.1.0">
    <infoTributaria>
        <ambiente>1</ambiente>
        <tipoEmision>1</tipoEmision>
        <razonSocial>PRUEBA S.A.</razonSocial>
        <nombreComercial>PRUEBA</nombreComercial>
        <ruc>1790000000001</ruc>
        <claveAcceso>0000000000000000000000000000000000000000000000000</claveAcceso>
        <codDoc>01</codDoc>
        <estab>001</estab>
        <ptoEmi>001</ptoEmi>
        <secuencial>000000001</secuencial>
        <dirMatriz>QUITO</dirMatriz>
    </infoTributaria>
    <infoFactura>
        <fechaEmision>01/01/2024</fechaEmision>
        <dirEstablecimiento>QUITO</dirEstablecimiento>
        <obligadoContabilidad>SI</obligadoContabilidad>
        <tipoIdentificacionComprador>04</tipoIdentificacionComprador>
        <razonSocialComprador>CLIENTE PRUEBA</razonSocialComprador>
        <identificacionComprador>9999999999</identificacionComprador>
        <totalSinImpuestos>100.00</totalSinImpuestos>
        <totalDescuento>0.00</totalDescuento>
        <totalConImpuestos>
            <totalImpuesto>
                <codigo>2</codigo>
                <codigoPorcentaje>2</codigoPorcentaje>
                <baseImponible>100.00</baseImponible>
                <valor>12.00</valor>
            </totalImpuesto>
        </totalConImpuestos>
        <propina>0.00</propina>
        <importeTotal>112.00</importeTotal>
        <moneda>DOLAR</moneda>
    </infoFactura>
    <detalles>
        <detalle>
            <codigoPrincipal>001</codigoPrincipal>
            <descripcion>PRODUCTO DE PRUEBA</descripcion>
            <cantidad>1</cantidad>
            <precioUnitario>100.00</precioUnitario>
            <descuento>0.00</descuento>
            <precioTotalSinImpuesto>100.00</precioTotalSinImpuesto>
            <impuestos>
                <impuesto>
                    <codigo>2</codigo>
                    <codigoPorcentaje>2</codigoPorcentaje>
                    <tarifa>12.00</tarifa>
                    <baseImponible>100.00</baseImponible>
                    <valor>12.00</valor>
                </impuesto>
            </impuestos>
        </detalle>
    </detalles>
</factura>"""
    
    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_content)
        return f.name

def validar_estructura_firma(xml_firmado_path):
    """Validar que la firma XAdES tenga la estructura correcta"""
    try:
        with open(xml_firmado_path, 'rb') as f:
            xml_data = f.read()
        
        doc = etree.fromstring(xml_data)
        
        # Verificar que existe la firma
        namespaces = {
            'ds': 'http://www.w3.org/2000/09/xmldsig#',
            'xades': 'http://uri.etsi.org/01903/v1.3.2#'
        }
        
        # Verificar elementos requeridos
        signature = doc.find('.//ds:Signature', namespaces)
        if signature is None:
            logger.error("No se encontró la firma en el XML")
            return False
            
        signed_info = signature.find('.//ds:SignedInfo', namespaces)
        signature_value = signature.find('.//ds:SignatureValue', namespaces)
        key_info = signature.find('.//ds:KeyInfo', namespaces)
        qualifying_properties = signature.find('.//xades:QualifyingProperties', namespaces)
        
        if not all([signed_info, signature_value, key_info, qualifying_properties]):
            logger.error("Faltan elementos requeridos en la firma")
            return False
            
        # Verificar que SignatureValue no sea placeholder
        if signature_value.text == "PLACEHOLDER_SIGNATURE_VALUE":
            logger.error("SignatureValue es un placeholder")
            return False
            
        logger.info("Estructura de firma XAdES válida")
        return True
        
    except Exception as e:
        logger.error(f"Error al validar estructura: {e}")
        return False

def main():
    """Función principal de prueba"""
    logger.info("=== Iniciando prueba de firma XAdES-BES ===")
    
    # Verificar que exista configuración de firma
    try:
        opciones = Opciones.objects.first()
        if not opciones or not opciones.firma_electronica or not opciones.password_firma:
            logger.error("No hay configuración de firma electrónica")
            return False
            
        logger.info(f"Certificado configurado: {opciones.firma_electronica}")
        
    except Exception as e:
        logger.error(f"Error al verificar configuración: {e}")
        return False
    
    # Crear XML de prueba
    xml_prueba = crear_xml_prueba()
    
    try:
        # Crear firmador
        firmador = SRIXAdESFirmador()
        
        # Crear archivo de salida temporal
        xml_firmado = xml_prueba.replace('.xml', '_firmado.xml')
        
        # Firmar XML
        logger.info("Firmando XML...")
        resultado = firmador.firmar_xml_xades_bes(xml_prueba, xml_firmado)
        
        if resultado:
            logger.info(f"XML firmado exitosamente: {xml_firmado}")
            
            # Validar estructura
            if validar_estructura_firma(xml_firmado):
                logger.info("✅ Prueba de firma XAdES-BES exitosa")
                
                # Mostrar tamaño de SignatureValue
                with open(xml_firmado, 'rb') as f:
                    content = f.read()
                doc = etree.fromstring(content)
                signature_value = doc.find('.//{http://www.w3.org/2000/09/xmldsig#}SignatureValue')
                if signature_value is not None and signature_value.text:
                    logger.info(f"SignatureValue length: {len(signature_value.text)} chars")
                    
                return True
            else:
                logger.error("❌ Estructura de firma inválida")
                return False
        else:
            logger.error("❌ Error al firmar XML")
            return False
            
    except XAdESError as e:
        logger.error(f"❌ Error XAdES: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        return False
    finally:
        # Limpiar archivos temporales
        for archivo in [xml_prueba, xml_prueba.replace('.xml', '_firmado.xml')]:
            if os.path.exists(archivo):
                os.unlink(archivo)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)