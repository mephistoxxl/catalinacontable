#!/usr/bin/env python3
"""
Script de prueba simple para validación XSD
"""

print("🧪 INICIANDO PRUEBA SIMPLE")
print("=" * 30)

try:
    import os
    import sys
    
    print("✅ Importaciones básicas OK")
    
    # Configurar Django
    sys.path.append(r'c:\Users\CORE I7\Desktop\sisfact')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
    
    print("✅ Configuración Django OK")
    
    import django
    django.setup()
    
    print("✅ Django setup OK")
    
    from inventario.sri.xml_generator import SRIXMLGenerator
    
    print("✅ SRIXMLGenerator importado OK")
    
    xml_gen = SRIXMLGenerator()
    
    print("✅ SRIXMLGenerator instanciado OK")
    
    # Verificar método de validación
    if hasattr(xml_gen, 'validar_xml_contra_xsd'):
        print("✅ Método validar_xml_contra_xsd encontrado")
    else:
        print("❌ Método validar_xml_contra_xsd NO encontrado")
    
    # Verificar archivos XSD
    xsd_file = r"c:\Users\CORE I7\Desktop\sisfact\inventario\sri\factura_V1.1.0.xsd"
    if os.path.exists(xsd_file):
        print("✅ Archivo XSD encontrado")
    else:
        print("❌ Archivo XSD NO encontrado")
        print(f"   Buscado en: {xsd_file}")
    
    print("\n🎉 PRUEBA SIMPLE COMPLETADA EXITOSAMENTE")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
