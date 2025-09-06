#!/usr/bin/env python
import os
import django
import json

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from django.core import serializers
from inventario.models import *

def backup_data():
    print("=== CREANDO BACKUP DE DATOS SQLITE ===")
    
    # Lista de modelos a exportar (evitando problemas con contenttypes)
    models_to_backup = [
        Usuario,
        Empresa,
        UsuarioEmpresa,
        Opciones,
        Cliente,
        Proveedor,
        Producto,
        Factura,
        DetalleFactura,
        Pedido,
        DetallePedido,
        FormaPago,
        Banco,
        Caja,
        Almacen,
        Secuencia,
        Facturador
    ]
    
    all_data = []
    
    for model in models_to_backup:
        try:
            print(f"Exportando {model.__name__}...")
            objects = model.objects.all()
            serialized = serializers.serialize('json', objects, use_natural_foreign_keys=True, use_natural_primary_keys=True)
            data = json.loads(serialized)
            all_data.extend(data)
            print(f"  ✅ {len(data)} registros exportados")
        except Exception as e:
            print(f"  ❌ Error exportando {model.__name__}: {e}")
    
    # Guardar en archivo
    with open('backup_sqlite_data.json', 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Backup completado: {len(all_data)} registros totales")
    print("📁 Archivo: backup_sqlite_data.json")

if __name__ == "__main__":
    backup_data()
