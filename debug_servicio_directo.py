import os
import sys
import django

# Agregar el directorio del proyecto al path
sys.path.append(r'C:\Users\CORE I7\Desktop\sisfact')

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Servicio

print("🔍 VERIFICACIÓN DIRECTA DEL SERVICIO S000000002")
print("="*60)

try:
    # Buscar el servicio específico
    servicio = Servicio.objects.filter(codigo__iexact='S000000002').first()
    
    if servicio:
        print(f"✅ SERVICIO ENCONTRADO")
        print(f"   Código: {servicio.codigo}")
        print(f"   Descripción: {servicio.descripcion}")
        print(f"   Precio: {servicio.precio1}")
        print(f"   IVA field (raw): {repr(servicio.iva)}")
        print(f"   IVA field (str): '{str(servicio.iva)}'")
        print(f"   IVA field type: {type(servicio.iva)}")
        
        # Probar el mapeo
        MAPEO_IVA = {
            '0': 0.00,  # Sin IVA
            '5': 0.05,  # 5%
            '2': 0.12,  # 12%
            '10': 0.13, # 13%
            '3': 0.14,  # 14%
            '4': 0.15,  # 15%
            '9': 0.16,  # 16% - Agregado para servicios
            '6': 0.00,  # Exento
            '7': 0.00,  # Exento
            '8': 0.08   # 8%
        }
        
        iva_code = str(servicio.iva) if servicio.iva else '2'
        iva_percent = MAPEO_IVA.get(iva_code, 0.12)
        precio_base = float(servicio.precio1) if servicio.precio1 else 0.0
        precio_con_iva = precio_base * (1 + iva_percent)
        
        print(f"\n📊 CÁLCULOS:")
        print(f"   IVA code: '{iva_code}'")
        print(f"   IVA percentage: {iva_percent} ({iva_percent*100}%)")
        print(f"   Precio base: ${precio_base}")
        print(f"   Precio con IVA: ${precio_con_iva}")
        
        # Verificaciones específicas
        if abs(precio_con_iva - 0.58) < 0.01:
            print(f"✅ COINCIDE CON DJANGO: ${precio_con_iva} ≈ $0.58")
        elif abs(precio_con_iva - 0.56) < 0.01:
            print(f"❌ COINCIDE CON JAVASCRIPT: ${precio_con_iva} ≈ $0.56")
        else:
            print(f"🤔 VALOR INESPERADO: ${precio_con_iva}")
            
        # Verificar si el IVA está en el mapeo
        if iva_code in MAPEO_IVA:
            print(f"✅ IVA code '{iva_code}' SÍ está en MAPEO_IVA")
        else:
            print(f"❌ IVA code '{iva_code}' NO está en MAPEO_IVA")
            
    else:
        print("❌ SERVICIO S000000002 NO ENCONTRADO")
        print("Buscando servicios similares...")
        servicios = Servicio.objects.filter(codigo__icontains='S000')[:5]
        for s in servicios:
            print(f"   - {s.codigo}: {s.descripcion}")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n🔍 VERIFICANDO TODOS LOS SERVICIOS CON PRECIO ~$0.5:")
print("="*60)
try:
    servicios = Servicio.objects.filter(precio1__gte=0.4, precio1__lte=0.6)[:10]
    for s in servicios:
        precio = float(s.precio1) if s.precio1 else 0.0
        print(f"   {s.codigo}: ${precio}, IVA: {repr(s.iva)}")
except Exception as e:
    print(f"❌ ERROR listando servicios: {e}")
