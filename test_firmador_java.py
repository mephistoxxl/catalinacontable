"""
Test para verificar que el firmador con JAR de Java funciona correctamente.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from inventario.sri.firmador_java import verificar_instalacion_java, firmar_xml_con_java
from inventario.models import Opciones
from pathlib import Path


def main():
    print("=" * 70)
    print("VERIFICACIÓN DEL FIRMADOR CON JAR DE JAVA")
    print("=" * 70)
    print()
    
    # 1. Verificar Java
    print("1️⃣  VERIFICANDO JAVA...")
    print("-" * 70)
    
    java_info = verificar_instalacion_java()
    
    if java_info['instalado']:
        print(f"✅ Java está instalado")
        print(f"   Versión: {java_info['version']}")
    else:
        print("❌ Java NO está instalado")
        print("   Por favor instala Java JRE 8 o superior desde:")
        print("   https://www.java.com/es/download/")
        return
    
    print()
    
    # 2. Verificar JAR
    print("2️⃣  VERIFICANDO JAR DE FIRMA...")
    print("-" * 70)
    
    if java_info['jar_disponible']:
        print(f"✅ JAR encontrado")
        print(f"   Ruta: {java_info['jar_path']}")
    else:
        print(f"❌ JAR NO encontrado")
        print(f"   Se esperaba en: {java_info['jar_path']}")
        return
    
    print()
    
    # 3. Verificar configuración
    print("3️⃣  VERIFICANDO CONFIGURACIÓN DE FIRMA...")
    print("-" * 70)
    
    try:
        opciones = Opciones.objects.first()
        if not opciones:
            print("❌ No hay configuración de Opciones en la base de datos")
            return
        
        print(f"✅ Configuración encontrada")
        print(f"   Empresa: {opciones.empresa}")
        print(f"   Certificado: {opciones.firma_electronica.name if opciones.firma_electronica else 'NO CONFIGURADO'}")
        
        if not opciones.firma_electronica:
            print("❌ No hay certificado P12 configurado")
            return
        
        print(f"   Certificado existe: {opciones.firma_electronica.storage.exists(opciones.firma_electronica.name)}")
        
    except Exception as e:
        print(f"❌ Error al verificar configuración: {e}")
        return
    
    print()
    
    # 4. Buscar XML de prueba
    print("4️⃣  BUSCANDO XML DE PRUEBA...")
    print("-" * 70)
    
    test_xml = None
    xml_candidates = [
        'test_factura.xml',
        'LiquidacionCompra_V1.1.0.xml',
        'inventario/aprovada.XML'
    ]
    
    for xml_file in xml_candidates:
        if os.path.exists(xml_file):
            test_xml = xml_file
            print(f"✅ XML de prueba encontrado: {xml_file}")
            break
    
    if not test_xml:
        print("❌ No se encontró ningún XML de prueba")
        print("   Archivos buscados:")
        for xml_file in xml_candidates:
            print(f"   - {xml_file}")
        return
    
    print()
    
    # 5. Probar firma
    print("5️⃣  PROBANDO FIRMA CON JAR DE JAVA...")
    print("-" * 70)
    
    output_xml = "test_firmado_java.xml"
    
    try:
        print(f"   XML entrada: {test_xml}")
        print(f"   XML salida: {output_xml}")
        print()
        print("   Firmando...")
        
        resultado = firmar_xml_con_java(
            test_xml,
            output_xml,
            opciones=opciones
        )
        
        if resultado:
            print()
            print("✅ ¡FIRMA EXITOSA CON JAR DE JAVA!")
            print()
            
            if os.path.exists(output_xml):
                # Leer y mostrar parte del XML firmado
                with open(output_xml, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                print(f"   Tamaño del XML firmado: {len(content)} bytes")
                
                # Verificar que tenga firma
                if '<ds:Signature' in content:
                    print("   ✅ Contiene elemento <ds:Signature>")
                else:
                    print("   ❌ NO contiene elemento <ds:Signature>")
                
                if '<ds:SignedInfo>' in content:
                    print("   ✅ Contiene elemento <ds:SignedInfo>")
                
                if '<ds:SignatureValue>' in content:
                    print("   ✅ Contiene elemento <ds:SignatureValue>")
                
                if '<ds:KeyInfo>' in content:
                    print("   ✅ Contiene elemento <ds:KeyInfo>")
                
                if '<xades:QualifyingProperties>' in content or 'QualifyingProperties' in content:
                    print("   ✅ Contiene propiedades XAdES")
                
                print()
                print(f"   📄 Revisa el archivo: {output_xml}")
        else:
            print("❌ La firma falló")
    
    except Exception as e:
        print(f"❌ Error durante la firma: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    print("=" * 70)
    print("VERIFICACIÓN COMPLETA")
    print("=" * 70)
    print()
    print("🔥 El firmador con JAR de Java está listo para usar")
    print("   Para usarlo, asegúrate de que USE_JAVA_SIGNER=true")
    print()


if __name__ == "__main__":
    main()
