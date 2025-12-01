"""
Script para crear los planes iniciales del sistema.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Plan
from decimal import Decimal

def crear_planes():
    """Crea los planes iniciales si no existen."""
    
    planes = [
        {
            'codigo': 'MICRO',
            'nombre': 'Plan Micro',
            'precio_base': Decimal('8.99'),
            'limite_documentos': 65,
            'frecuencia': 'ANUAL',
            'descripcion': 'Plan ideal para microempresas. Incluye hasta 65 documentos al año (facturas, guías de remisión, liquidaciones de compra).',
        },
        {
            'codigo': 'BASICO',
            'nombre': 'Plan Básico',
            'precio_base': Decimal('12.99'),
            'limite_documentos': 100,
            'frecuencia': 'ANUAL',
            'descripcion': 'Plan para pequeñas empresas. Incluye hasta 100 documentos al año.',
        },
        {
            'codigo': 'EMPRENDEDOR',
            'nombre': 'Plan Emprendedor',
            'precio_base': Decimal('15.99'),
            'limite_documentos': 150,
            'frecuencia': 'ANUAL',
            'descripcion': 'Plan para empresas en crecimiento. Incluye hasta 150 documentos al año.',
        },
        {
            'codigo': 'EXTRA',
            'nombre': 'Opción Extra',
            'precio_base': Decimal('6.99'),
            'limite_documentos': 50,
            'frecuencia': 'MENSUAL',
            'descripcion': 'Paquete adicional de documentos. Se puede agregar a cualquier plan cuando se necesiten más documentos.',
        },
    ]
    
    planes_creados = 0
    planes_existentes = 0
    
    for plan_data in planes:
        plan, created = Plan.objects.get_or_create(
            codigo=plan_data['codigo'],
            defaults=plan_data
        )
        
        if created:
            planes_creados += 1
            precio_con_iva = plan.precio_con_iva
            print(f"✅ Plan '{plan.nombre}' creado exitosamente")
            print(f"   - Código: {plan.codigo}")
            print(f"   - Precio base: ${plan.precio_base}")
            print(f"   - Precio con IVA (15%): ${precio_con_iva}")
            print(f"   - Límite de documentos: {plan.limite_documentos}")
            print(f"   - Frecuencia: {plan.get_frecuencia_display()}")
            print()
        else:
            planes_existentes += 1
            print(f"ℹ️  Plan '{plan.nombre}' ya existe en el sistema")
    
    print("\n" + "="*60)
    print(f"Resumen:")
    print(f"- Planes creados: {planes_creados}")
    print(f"- Planes ya existentes: {planes_existentes}")
    print(f"- Total de planes en el sistema: {Plan.objects.count()}")
    print("="*60)
    
    if planes_creados > 0:
        print("\n🎉 Los planes han sido creados exitosamente!")
        print("Ahora puedes asignarlos a empresas desde el Django Admin:")
        print("   👉 /admin/inventario/empresaplan/")

if __name__ == '__main__':
    print("Creando planes iniciales del sistema...")
    print("="*60)
    print()
    crear_planes()
