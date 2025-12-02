import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura, DetalleFactura, FormaPago

# Ver configuración de base de datos y facturas
from django.conf import settings
print(f"DATABASE: {settings.DATABASES['default']['NAME']}")

# Buscar TODAS las facturas (sin filtro de empresa)
from inventario.models import Factura, DetalleFactura, FormaPago, Empresa

print(f"\nEmpresas: {Empresa.objects.count()}")
for e in Empresa.objects.all():
    print(f"  - ID {e.id}: {e.razon_social}")

# Usar el manager sin filtro de tenant
facturas = Factura.objects.using('default').all().order_by('-id')[:10]

print(f"\nTotal facturas (sin filtro): {Factura.objects.using('default').count()}\n")

for factura in facturas:
    print(f"\n{'='*60}")
    print(f"FACTURA ID: {factura.id}")
    print(f"Establecimiento: {factura.establecimiento}")
    print(f"Punto Emisión: {factura.punto_emision}")
    print(f"Secuencia: {factura.secuencia}")
    print(f"{'='*60}")
    print(f"identificacion_cliente: '{factura.identificacion_cliente}'")
    print(f"nombre_cliente: '{factura.nombre_cliente}'")
    print(f"Almacén ID: {factura.almacen_id}")
    print(f"Monto general: ${factura.monto_general}")
    
    detalles = DetalleFactura.objects.filter(factura=factura)
    print(f"\nDetalles ({detalles.count()}):")
    for d in detalles:
        print(f"  - Producto ID: {d.producto_id}")
        if d.producto:
            print(f"    * codigo: '{d.producto.codigo}'")
            print(f"    * descripcion: '{d.producto.descripcion}'")
        print(f"  - descripcion (texto): '{d.descripcion}'")
        print(f"  - cantidad: {d.cantidad}")
        print(f"  - precio_unitario: {d.precio_unitario}")
        print(f"  - tarifa_iva: {d.tarifa_iva}")
    
    pagos = FormaPago.objects.filter(factura=factura)
    print(f"\nFormas de Pago ({pagos.count()}):")
    for p in pagos:
        print(f"  - {p.forma_pago}: ${p.total}")

print(f"\n{'='*60}\n")
