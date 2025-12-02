import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')

# Cargar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from inventario.models import DetalleFactura

# Obtener el último detalle
d = DetalleFactura.objects.order_by('-id').first()

if d:
    print("=" * 50)
    print(f"Factura: {d.factura.secuencial}")
    print(f"Producto: {d.producto}")
    print("=" * 50)
    print(f"precio_unitario en DetalleFactura: {d.precio_unitario}")
    print(f"sub_total en DetalleFactura: {d.sub_total}")
    print(f"total en DetalleFactura: {d.total}")
    print("=" * 50)
    if d.producto:
        print(f"Precio ORIGINAL del producto: {d.producto.precio}")
    print("=" * 50)
else:
    print("No hay detalles de factura")
