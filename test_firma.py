#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

print('🔧 Diagnóstico Detallado de Firma XML')
print('=' * 50)

try:
    from inventario.sri.firmador import firmar_xml
    from inventario.models import Factura, Opciones
    
    # Verificar configuración de firma
    opciones = Opciones.objects.first()
    if not opciones:
        print('❌ No hay configuración de Opciones')
    elif not opciones.firma_electronica:
        print('❌ No hay archivo de firma electrónica configurado')
    elif not opciones.password_firma:
        print('❌ No hay contraseña de firma configurada')
    else:
        print(f'✅ Configuración firma OK: {opciones.firma_electronica.name}')
        
        # Crear XML de prueba
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<factura>
    <infoTributaria>
        <claveAcceso>1234567890123456789012345678901234567890123456789</claveAcceso>
    </infoTributaria>
    <infoFactura>
        <totalSinImpuestos>100.00</totalSinImpuestos>
    </infoFactura>
</factura>"""
        
        test_xml = 'test_firma.xml'
        test_xml_firmado = 'test_firma_firmado.xml'
        
        with open(test_xml, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        print(f'📄 XML original creado: {os.path.getsize(test_xml)} bytes')
        
        # Intentar firmar
        firmar_xml(test_xml, test_xml_firmado)
        
        # Analizar resultado
        if os.path.exists(test_xml_firmado):
            size = os.path.getsize(test_xml_firmado)
            print(f'📄 XML firmado: {size} bytes')
            
            with open(test_xml_firmado, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Buscar elementos de firma
            elementos_firma = [
                '<Signature',
                '<ds:Signature', 
                'xmlns:ds=',
                '<SignedInfo',
                '<CanonicalizationMethod',
                '<SignatureValue'
            ]
            
            print('🔍 Análisis de contenido firmado:')
            for elemento in elementos_firma:
                if elemento in content:
                    print(f'   ✅ {elemento} - PRESENTE')
                else:
                    print(f'   ❌ {elemento} - AUSENTE')
            
            # Mostrar primeras líneas del XML firmado
            lineas = content.split('\n')[:10]
            print(f'\\n� Primeras líneas del XML firmado:')
            for i, linea in enumerate(lineas, 1):
                print(f'   {i:2}: {linea[:80]}')
            
        # Limpiar
        for archivo in [test_xml, test_xml_firmado]:
            if os.path.exists(archivo):
                os.remove(archivo)
        
except Exception as e:
    print(f'❌ ERROR: {str(e)}')
    import traceback
    print('Traceback completo:')
    print(traceback.format_exc())
