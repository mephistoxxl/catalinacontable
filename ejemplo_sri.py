#!/usr/bin/env python3
"""
Ejemplo de uso del cliente SRI para facturación electrónica
Este script demuestra cómo enviar y autorizar comprobantes electrónicos
"""

import os
import sys
import logging
from datetime import datetime

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from inventario.sri.sri_client import SRIClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def crear_xml_ejemplo():
    """Crea un XML de ejemplo para pruebas"""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.1.0">
    <infoTributaria>
        <ambiente>1</ambiente>
        <tipoEmision>1</tipoEmision>
        <razonSocial>EMPRESA DE PRUEBA S.A.</razonSocial>
        <nombreComercial>EMPRESA DE PRUEBA</nombreComercial>
        <ruc>1790000000001</ruc>
        <claveAcceso>0104202401179000000010010010000000000010000000113</claveAcceso>
        <codDoc>01</codDoc>
        <estab>001</estab>
        <ptoEmi>001</ptoEmi>
        <secuencial>000000001</secuencial>
        <dirMatriz>QUITO</dirMatriz>
    </infoTributaria>
    <infoFactura>
        <fechaEmision>01/04/2024</fechaEmision>
        <dirEstablecimiento>QUITO</dirEstablecimiento>
        <obligadoContabilidad>SI</obligadoContabilidad>
        <tipoIdentificacionComprador>04</tipoIdentificacionComprador>
        <razonSocialComprador>CLIENTE DE PRUEBA</razonSocialComprador>
        <identificacionComprador>1710036156001</identificacionComprador>
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
    return xml_content

def ejemplo_envio_individual():
    """Ejemplo de envío individual de un comprobante"""
    print("=== EJEMPLO DE ENVÍO INDIVIDUAL ===")
    
    # Crear cliente SRI (ambiente de pruebas)
    cliente = SRIClient(ambiente='pruebas')
    
    # Verificar servicios
    print("Verificando servicios SRI...")
    estado_servicios = cliente.verificar_servicio()
    print(f"Estado servicios: {estado_servicios}")
    
    # Usar XML de ejemplo
    xml_content = crear_xml_ejemplo()
    clave_acceso = "0104202401179000000010010010000000000010000000113"
    
    # Guardar XML temporalmente
    ruta_xml = f"factura_ejemplo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
    with open(ruta_xml, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    
    print(f"XML guardado en: {ruta_xml}")
    
    try:
        # Enviar comprobante
        print("Enviando comprobante al SRI...")
        resultado = cliente.enviar_comprobante(xml_content, clave_acceso)
        
        print(f"Estado del envío: {resultado['estado']}")
        
        if resultado['mensajes']:
            print("Mensajes del SRI:")
            for msg in resultado['mensajes']:
                print(f"  - {msg['identificador']}: {msg['mensaje']} ({msg['tipo']})")
        
        # Si fue recibido, consultar autorización
        if resultado['estado'] == 'RECIBIDA':
            print("Comprobante recibido, consultando autorización...")
            resultado_auto = cliente.consultar_autorizacion(clave_acceso)
            
            print(f"Estado de autorización: {resultado_auto['estado']}")
            
            if resultado_auto['autorizaciones']:
                for aut in resultado_auto['autorizaciones']:
                    print(f"Número de autorización: {aut['numeroAutorizacion']}")
                    print(f"Fecha de autorización: {aut['fechaAutorizacion']}")
                    print(f"Ambiente: {aut['ambiente']}")
        
    except Exception as e:
        print(f"Error al procesar: {e}")

def ejemplo_proceso_completo():
    """Ejemplo de proceso completo con reintentos"""
    print("\n=== EJEMPLO DE PROCESO COMPLETO ===")
    
    cliente = SRIClient(ambiente='pruebas')
    xml_content = crear_xml_ejemplo()
    clave_acceso = "0104202401179000000010010010000000000010000000113"
    
    try:
        print("Iniciando proceso completo...")
        resultado = cliente.procesar_comprobante_completo(
            xml_content, 
            clave_acceso,
            max_intentos=3,
            espera_segundos=2
        )
        
        print(f"Resultado final: {resultado['estado']}")
        
        if resultado['estado'] == 'AUTORIZADO':
            print("✅ Comprobante autorizado exitosamente!")
            if resultado['autorizaciones']:
                aut = resultado['autorizaciones'][0]
                print(f"Número de autorización: {aut['numeroAutorizacion']}")
                print(f"Fecha: {aut['fechaAutorizacion']}")
        elif resultado['estado'] == 'NO AUTORIZADO':
            print("❌ Comprobante no autorizado")
        elif resultado['estado'] == 'PENDIENTE':
            print("⏳ Autorización pendiente")
        else:
            print(f"⚠️ Estado desconocido: {resultado['estado']}")
            
        if resultado['mensajes']:
            print("Mensajes:")
            for msg in resultado['mensajes']:
                print(f"  - [{msg['tipo']}] {msg['mensaje']}")
                
    except Exception as e:
        print(f"Error en proceso completo: {e}")

def procesar_xml_desde_archivo(ruta_xml):
    """Procesar un XML desde archivo"""
    print(f"\n=== PROCESAR XML DESDE ARCHIVO ===")
    print(f"Archivo: {ruta_xml}")
    
    try:
        with open(ruta_xml, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        # Extraer clave de acceso del XML
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_content)
        clave_acceso = root.find('.//claveAcceso').text
        
        print(f"Clave de acceso: {clave_acceso}")
        
        cliente = SRIClient(ambiente='pruebas')
        resultado = cliente.procesar_comprobante_completo(xml_content, clave_acceso)
        
        return resultado
        
    except FileNotFoundError:
        print(f"Error: Archivo {ruta_xml} no encontrado")
        return None
    except Exception as e:
        print(f"Error al procesar archivo: {e}")
        return None

def menu_principal():
    """Menú interactivo"""
    while True:
        print("\n" + "="*50)
        print("SISTEMA DE FACTURACIÓN ELECTRÓNICA SRI")
        print("="*50)
        print("1. Enviar comprobante de ejemplo")
        print("2. Proceso completo con reintentos")
        print("3. Procesar XML desde archivo")
        print("4. Verificar servicios SRI")
        print("5. Salir")
        
        opcion = input("\nSeleccione una opción: ").strip()
        
        if opcion == '1':
            ejemplo_envio_individual()
        elif opcion == '2':
            ejemplo_proceso_completo()
        elif opcion == '3':
            ruta = input("Ruta del archivo XML: ").strip()
            if ruta:
                procesar_xml_desde_archivo(ruta)
        elif opcion == '4':
            cliente = SRIClient(ambiente='pruebas')
            estado = cliente.verificar_servicio()
            print("\nEstado de servicios SRI:")
            print(f"Recepción: {'✅ Disponible' if estado['recepcion']['disponible'] else '❌ No disponible'}")
            print(f"Autorización: {'✅ Disponible' if estado['autorizacion']['disponible'] else '❌ No disponible'}")
            if estado['recepcion']['error']:
                print(f"Error recepción: {estado['recepcion']['error']}")
            if estado['autorizacion']['error']:
                print(f"Error autorización: {estado['autorizacion']['error']}")
        elif opcion == '5':
            print("¡Hasta luego!")
            break
        else:
            print("Opción no válida")

if __name__ == "__main__":
    print("Ejemplos de integración con SRI - Ecuador")
    print("=" * 50)
    
    # Ejecutar ejemplo rápido
    print("Ejecutando ejemplo de proceso completo...")
    ejemplo_proceso_completo()
    
    # Preguntar si desea menú interactivo
    continuar = input("\n¿Desea ejecutar el menú interactivo? (s/n): ").strip().lower()
    if continuar == 's':
        menu_principal()