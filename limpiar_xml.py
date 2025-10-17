#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import glob

# Borrar XMLs corruptos de factura 23
xml_pattern = "media/facturas/2390054060001/xml/factura_001*000000023*.xml"
for xml_file in glob.glob(xml_pattern):
    try:
        os.remove(xml_file)
        print(f"✅ Eliminado: {xml_file}")
    except Exception as e:
        print(f"❌ Error eliminando {xml_file}: {e}")

print("\n✅ Limpieza completada")
print("\nAHORA:")
print("1. Abre http://localhost:8000")
print("2. Crea una NUEVA factura (número 24)")
print("3. Firma y envía")
print("4. El XML ahora se generará con lxml (UTF-8 correcto)")
