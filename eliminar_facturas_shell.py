from inventario.models import Empresa, Factura
from django.db import transaction

RUC = '1713959011001'

empresa = Empresa.objects.filter(ruc=RUC).first()
if not empresa:
    print(f"No se encontró empresa con RUC {RUC}")
else:
    print(f"Empresa: {empresa.razon_social}")
    facturas = Factura._unsafe_objects.filter(empresa=empresa)
    total = facturas.count()
    print(f"Facturas a eliminar: {total}")
    
    if total > 0:
        confirm = input("Escriba ELIMINAR para confirmar: ")
        if confirm == "ELIMINAR":
            with transaction.atomic():
                deleted, details = facturas.delete()
                print(f"\nEliminados {deleted} registros:")
                for model, count in details.items():
                    print(f"  {model}: {count}")
        else:
            print("Cancelado")
