#!/usr/bin/env python3
"""
Script para verificar y crear datos de prueba para el sistema de proformas
"""
import os
import sys
import django

# Configurar Django
if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
    sys.path.append('c:/Users/CORE I7/Desktop/sisfact')
    django.setup()
    
    from inventario.models import Almacen, Facturador, Empresa
    
    print("=== VERIFICACIÓN DE DATOS PARA PROFORMAS ===\n")
    
    # Verificar empresas
    empresas = Empresa.objects.all()
    print(f"Empresas encontradas: {empresas.count()}")
    if empresas.exists():
        for empresa in empresas:
            print(f"  - {empresa.razon_social} (ID: {empresa.id})")
    print()
    
    # Verificar almacenes
    almacenes = Almacen.objects.all()
    print(f"Almacenes totales: {almacenes.count()}")
    almacenes_activos = Almacen.objects.filter(activo=True)
    print(f"Almacenes activos: {almacenes_activos.count()}")
    
    if almacenes.exists():
        for almacen in almacenes:
            estado = "✅ Activo" if almacen.activo else "❌ Inactivo"
            empresa_info = f" - Empresa: {almacen.empresa}" if almacen.empresa else " - Sin empresa"
            print(f"  - {almacen.descripcion} (ID: {almacen.id}) {estado}{empresa_info}")
    else:
        print("  ⚠️  No hay almacenes en la base de datos")
    print()
    
    # Verificar facturadores
    facturadores = Facturador.objects.all()
    print(f"Facturadores totales: {facturadores.count()}")
    facturadores_activos = Facturador.objects.filter(activo=True)
    print(f"Facturadores activos: {facturadores_activos.count()}")
    
    if facturadores.exists():
        for facturador in facturadores:
            estado = "✅ Activo" if facturador.activo else "❌ Inactivo"
            empresa_info = f" - Empresa: {facturador.empresa}" if facturador.empresa else " - Sin empresa"
            print(f"  - {facturador.nombres} (ID: {facturador.id}) {estado}{empresa_info}")
    else:
        print("  ⚠️  No hay facturadores en la base de datos")
    print()
    
    # Crear datos de prueba si no existen
    if not almacenes_activos.exists():
        print("🔧 Creando almacenes de prueba...")
        empresa_principal = empresas.first() if empresas.exists() else None
        
        Almacen.objects.get_or_create(
            descripcion="Almacén Principal",
            defaults={'activo': True, 'empresa': empresa_principal}
        )
        Almacen.objects.get_or_create(
            descripcion="Almacén Secundario",
            defaults={'activo': True, 'empresa': empresa_principal}
        )
        print("✅ Almacenes de prueba creados")
    
    if not facturadores_activos.exists():
        print("🔧 Creando facturadores de prueba...")
        empresa_principal = empresas.first() if empresas.exists() else None
        
        try:
            facturador1, created1 = Facturador.objects.get_or_create(
                correo="facturador1@test.com",
                defaults={
                    'nombres': "Juan Pérez",
                    'activo': True,
                    'empresa': empresa_principal,
                    'telefono': '0999999999'
                }
            )
            if created1:
                facturador1.set_password("123456")
                facturador1.save()
            
            facturador2, created2 = Facturador.objects.get_or_create(
                correo="facturador2@test.com",
                defaults={
                    'nombres': "María López",
                    'activo': True,
                    'empresa': empresa_principal,
                    'telefono': '0988888888'
                }
            )
            if created2:
                facturador2.set_password("123456")
                facturador2.save()
                
            print("✅ Facturadores de prueba creados")
        except Exception as e:
            print(f"❌ Error creando facturadores: {e}")
    
    print("\n=== VERIFICACIÓN FINAL ===")
    almacenes_final = Almacen.objects.filter(activo=True).count()
    facturadores_final = Facturador.objects.filter(activo=True).count()
    
    print(f"✅ Almacenes activos disponibles: {almacenes_final}")
    print(f"✅ Facturadores activos disponibles: {facturadores_final}")
    
    if almacenes_final > 0 and facturadores_final > 0:
        print("\n🎉 ¡Los dropdowns deberían funcionar correctamente ahora!")
    else:
        print("\n⚠️  Es posible que los dropdowns sigan vacíos. Revisa la configuración.")
