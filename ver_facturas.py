import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura

facturas = Factura.objects.all()[:10]
print(f'Total facturas: {Factura.objects.count()}')
for f in facturas:
    estado = f.estado_sri or "SIN ESTADO"
    print(f'ID:{f.id} | Número:{f.numero} | Estado:{estado} | Cliente:{f.nombre_cliente}')
