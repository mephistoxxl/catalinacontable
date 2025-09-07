#!/usr/bin/env python
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
os.environ['USE_POSTGRESQL'] = 'true'
django.setup()

from inventario.models import *
from django.db import transaction

def load_data_safely():
    print("=== CARGA MANUAL DE DATOS A POSTGRESQL ===")
    
    with open('backup_sqlite_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Agrupar por modelo
    models_data = {}
    for item in data:
        model_name = item['model']
        if model_name not in models_data:
            models_data[model_name] = []
        models_data[model_name].append(item)
    
    # Orden de carga para respetar dependencias
    load_order = [
        'inventario.empresa',
        'inventario.usuario', 
        'inventario.usuarioempresa',
        'inventario.opciones',
        'inventario.cliente',
        'inventario.proveedor',
        'inventario.producto',
        'inventario.factura',
        'inventario.detallefactura',
        'inventario.formapago',
        'inventario.banco',
        'inventario.caja',
        'inventario.almacen',
        'inventario.secuencia',
        'inventario.facturador'
    ]
    
    with transaction.atomic():
        for model_name in load_order:
            if model_name in models_data:
                items = models_data[model_name]
                print(f"Cargando {model_name}: {len(items)} registros...")
                
                for item in items:
                    try:
                        fields = item['fields']
                        
                        if model_name == 'inventario.empresa':
                            obj, created = Empresa.objects.get_or_create(
                                id=item['pk'],
                                defaults=fields
                            )
                            
                        elif model_name == 'inventario.usuario':
                            # Cargar usuario sin la relación empresas
                            empresas = fields.pop('empresas', [])
                            obj, created = Usuario.objects.get_or_create(
                                id=item['pk'],
                                defaults=fields
                            )
                            
                        elif model_name == 'inventario.usuarioempresa':
                            obj, created = UsuarioEmpresa.objects.get_or_create(
                                id=item['pk'],
                                defaults=fields
                            )
                            
                        elif model_name == 'inventario.opciones':
                            obj, created = Opciones.objects.get_or_create(
                                id=item['pk'],
                                defaults=fields
                            )
                            
                        elif model_name == 'inventario.cliente':
                            obj, created = Cliente.objects.get_or_create(
                                id=item['pk'],
                                defaults=fields
                            )
                            
                        else:
                            print(f"  Saltando {model_name} (no implementado)")
                            continue
                            
                        if created:
                            print(f"  ✅ Creado: {obj}")
                        else:
                            print(f"  ℹ️  Ya existe: {obj}")
                            
                    except Exception as e:
                        print(f"  ❌ Error con {item['pk']}: {e}")
    
    # Verificar resultados
    print("\n=== RESULTADOS ===")
    print(f"Usuarios: {Usuario.objects.count()}")
    print(f"Empresas: {Empresa.objects.count()}")
    print(f"Clientes: {Cliente.objects.count()}")

if __name__ == "__main__":
    load_data_safely()
