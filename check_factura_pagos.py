import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
import django
django.setup()

from inventario.models import Factura

factura = Factura.objects.get(id=92)
print("=== FACTURA 92 - Campos de pago ===")

# Ver todos los campos de la factura
for field in factura._meta.get_fields():
    field_name = field.name
    try:
        value = getattr(factura, field_name, None)
        if value and 'pago' in field_name.lower():
            print(f"  {field_name}: {value}")
    except:
        pass

# Ver campos relacionados
print("\n=== Relaciones ===")
print(f"  formas_pago (FK inverso): {factura.formapago_set.all()}")

# Ver todos los campos con valor
print("\n=== Campos con valor ===")
for field in ['id', 'monto_general', 'sub_monto', 'base_imponible']:
    print(f"  {field}: {getattr(factura, field, None)}")
