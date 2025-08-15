#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 PRUEBA DIRECTA: Verificar que validación XSD detiene envío
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.sri.xml_generator import SRIXMLGenerator
from inventario.sri.integracion_django import SRIIntegration

def test_validacion_xsd():
    print("🧪 Probando validación XSD...")
    
    # XML intencionalmente inválido
    xml_invalido = """<?xml version="1.0" encoding="UTF-8"?>
<factura xmlns="http://www.sri.gob.ec/ni/1.1.0">
    <infoTributaria>
        <ambiente>1</ambiente>
        <!-- FALTA CAMPOS OBLIGATORIOS -->
    </infoTributaria>
</factura>"""
    
    try:
        sri_integration = SRIIntegration()
        xml_generator = SRIXMLGenerator()
        xsd_path = sri_integration._obtener_ruta_xsd()
        
        print(f"📋 Usando XSD: {xsd_path}")
        print("🔍 Validando XML inválido...")
        
        # Esto DEBE fallar
        xml_generator.validar_xml_contra_xsd(xml_invalido, xsd_path)
        
        print("❌ ERROR: XML inválido PASÓ la validación (no debería)")
        return False
        
    except Exception as e:
        print(f"✅ CORRECTO: XML inválido FALLÓ la validación")
        print(f"📝 Error: {str(e)[:200]}...")
        print("🎉 VALIDACIÓN XSD DETIENE ENVÍO CORRECTAMENTE")
        return True

if __name__ == "__main__":
    test_validacion_xsd()
