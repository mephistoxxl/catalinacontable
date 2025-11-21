import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import GuiaRemision, Opciones
from inventario.guia_remision.xml_generator_guia import XMLGeneratorGuiaRemision

# ID de la guía a actualizar
GUIA_ID = 9  # Cambia esto si es otro ID

# Obtener la guía
guia = GuiaRemision.objects.get(id=GUIA_ID)
print(f"Guía: {guia.numero_completo}")
print(f"Clave antigua: {guia.clave_acceso}")

# Regenerar clave de acceso
opciones = Opciones.objects.filter(empresa=guia.empresa).first()
if not opciones:
    print("❌ ERROR: No hay opciones para esta empresa")
else:
    xml_gen = XMLGeneratorGuiaRemision(guia, guia.empresa, opciones)
    nueva_clave = xml_gen.generar_clave_acceso()
    
    guia.clave_acceso = nueva_clave
    guia.save()
    
    print(f"✅ Clave nueva: {guia.clave_acceso}")
    print(f"Longitud: {len(guia.clave_acceso)} dígitos")


