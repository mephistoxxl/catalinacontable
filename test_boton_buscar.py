#!/usr/bin/env python
"""
Test rápido para verificar que el botón de buscar cliente funciona
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Cliente

def test_buscar_cliente():
    print("=== TEST BÚSQUEDA DE CLIENTE ===")
    
    # Ver si hay clientes en la BD
    clientes = Cliente.objects.all()[:5]
    print(f"Total clientes en BD: {Cliente.objects.count()}")
    
    if clientes:
        for cliente in clientes:
            print(f"- {cliente.identificacion}: {cliente.razon_social}")
        
        # Test con primer cliente
        primer_cliente = clientes[0]
        print(f"\nProbando con: {primer_cliente.identificacion}")
        
        # Simular la consulta que hace el botón
        from django.http import JsonResponse
        from django.db.models import Q
        
        q = primer_cliente.identificacion
        try:
            cliente = Cliente.objects.get(
                Q(identificacion=q) | Q(ruc=q)
            )
            print(f"✅ Cliente encontrado: {cliente.razon_social}")
            print(f"   ID: {cliente.id}")
            print(f"   Correo: {cliente.correo}")
        except Cliente.DoesNotExist:
            print("❌ Cliente no encontrado")
    else:
        print("No hay clientes en la base de datos")

if __name__ == "__main__":
    test_buscar_cliente()
