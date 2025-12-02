import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
import django
django.setup()

from inventario.models import FormaPago

print("=== FORMAS PAGO FACTURA 92 ===")
fps = FormaPago.objects.filter(factura_id=92)
for fp in fps:
    print(f"  id={fp.id}, codigo_sri={fp.codigo_sri}, valor={fp.valor}, plazo={fp.plazo}")

# Ver columnas de FormaPago
print("\n=== COLUMNAS FormaPago ===")
for field in FormaPago._meta.get_fields():
    print(f"  {field.name}")
