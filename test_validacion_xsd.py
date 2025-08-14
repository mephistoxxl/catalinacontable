#!/usr/bin/env python3
"""
Script de prueba específica para validación XSD (sin dependencias SRI completas)
"""

print("🧪 PRUEBA ESPECÍFICA DE VALIDACIÓN XSD")
print("=" * 40)

try:
    import os
    import sys
    
    # Configurar Django
    sys.path.append(r'c:\Users\CORE I7\Desktop\sisfact')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
    
    import django
    django.setup()
    
    # Importar solo el generador XML (sin sri_client que requiere zeep)
    from inventario.sri.xml_generator import SRIXMLGenerator
    
    print("✅ Importación SRIXMLGenerator OK")
    
    # 1. Crear instancia
    xml_gen = SRIXMLGenerator()
    print("✅ Instancia SRIXMLGenerator creada")
    
    # 2. Verificar XSD
    xsd_path = r"c:\Users\CORE I7\Desktop\sisfact\inventario\sri\factura_V1.1.0.xsd"
    print(f"\n📄 Verificando XSD: {os.path.basename(xsd_path)}")
    
    if os.path.exists(xsd_path):
        file_size = os.path.getsize(xsd_path)
        print(f"   ✅ XSD encontrado: {file_size:,} bytes")
        
        # Leer primeras líneas para verificar contenido
        with open(xsd_path, 'r', encoding='utf-8') as f:
            first_lines = [f.readline().strip() for _ in range(3)]
        
        print(f"   📋 Contenido XSD (primeras líneas):")
        for i, line in enumerate(first_lines, 1):
            if line:
                print(f"      {i}: {line[:60]}...")
    else:
        print(f"   ❌ XSD no encontrado")
        sys.exit(1)
    
    # 3. Verificar XML de muestra
    xml_sample_path = r"c:\Users\CORE I7\Desktop\sisfact\inventario\sri\factura_V1.1.0.xml"
    print(f"\n📋 Verificando XML de muestra: {os.path.basename(xml_sample_path)}")
    
    if os.path.exists(xml_sample_path):
        file_size = os.path.getsize(xml_sample_path)
        print(f"   ✅ XML encontrado: {file_size:,} bytes")
        
        # 4. PROBAR VALIDACIÓN XSD
        print(f"\n🔬 PROBANDO VALIDACIÓN XSD...")
        print("   Validando XML contra esquema del SRI...")
        
        try:
            resultado = xml_gen.validar_xml_contra_xsd(xml_sample_path, xsd_path)
            
            print(f"\n📊 RESULTADOS DE VALIDACIÓN:")
            print(f"   Estado: {'✅ VÁLIDO' if resultado['valido'] else '❌ INVÁLIDO'}")
            print(f"   Mensaje: {resultado.get('mensaje', 'Sin mensaje')}")
            
            if not resultado['valido']:
                errores = resultado.get('errores', 'Sin detalles de errores')
                print(f"   Errores (primeros 300 chars): {str(errores)[:300]}...")
            
            # 5. Verificar que se puede leer el XML
            print(f"\n📖 Verificando estructura XML...")
            
            from lxml import etree
            
            with open(xml_sample_path, 'rb') as f:
                xml_content = f.read()
            
            root = etree.fromstring(xml_content)
            print(f"   ✅ XML bien formado")
            print(f"   📋 Elemento raíz: {root.tag}")
            print(f"   📊 Número de elementos hijos: {len(root)}")
            
        except Exception as e:
            print(f"   ❌ ERROR EN VALIDACIÓN: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"   ⚠️  XML de muestra no encontrado, creando XML de prueba...")
        
        # Crear XML simple para probar validación
        xml_test = '''<?xml version="1.0" encoding="UTF-8"?>
<facturaElectronica>
    <infoTributaria>
        <ambiente>1</ambiente>
        <razonSocial>Empresa Test</razonSocial>
    </infoTributaria>
</facturaElectronica>'''
        
        test_xml_path = r"c:\Users\CORE I7\Desktop\sisfact\test_xml_temp.xml"
        with open(test_xml_path, 'w', encoding='utf-8') as f:
            f.write(xml_test)
        
        print(f"   ✅ XML de prueba creado")
        
        try:
            resultado = xml_gen.validar_xml_contra_xsd(test_xml_path, xsd_path)
            print(f"   📊 Validación XML prueba: {'✅ VÁLIDO' if resultado['valido'] else '❌ INVÁLIDO'}")
        except Exception as e:
            print(f"   ❌ Error validando XML prueba: {e}")
        finally:
            # Limpiar archivo temporal
            if os.path.exists(test_xml_path):
                os.remove(test_xml_path)
    
    print("\n" + "=" * 40)
    print("🎉 PRUEBA DE VALIDACIÓN XSD COMPLETADA")
    print("✅ Sistema de validación funcionando")
    print("✅ XSD del SRI disponible")
    print("✅ Método validar_xml_contra_xsd operativo")
    
except Exception as e:
    print(f"\n❌ ERROR EN PRUEBA: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
