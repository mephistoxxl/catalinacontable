import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Empresa, Opciones

print("\n=== VERIFICACIÓN DE AMBIENTES ===\n")

for empresa in Empresa.objects.all():
    print(f"Empresa: {empresa.razon_social}")
    print(f"  RUC: {empresa.ruc}")
    print(f"  Ambiente Empresa: {empresa.tipo_ambiente} ({empresa.ambiente_descripcion})")
    
    opciones = Opciones.objects.filter(empresa=empresa).first()
    if opciones:
        print(f"  Ambiente Opciones: {opciones.tipo_ambiente} ({opciones.ambiente_descripcion})")
    else:
        print(f"  ⚠️ No tiene Opciones configuradas")
    print()
