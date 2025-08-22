#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para migrar los datos de proveedor de los campos antiguos a los nuevos.
Este script debe ejecutarse después de aplicar la migración 0073.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sisfact.settings')
django.setup()

from inventario.models import Proveedor

def migrar_datos_proveedor():
    """
    Migra los datos de los campos antiguos a los nuevos campos del modelo Proveedor
    """
    print("🔄 Iniciando migración de datos de proveedor...")
    
    try:
        # Obtener todos los proveedores
        proveedores = Proveedor.objects.all()
        total_proveedores = proveedores.count()
        
        if total_proveedores == 0:
            print("ℹ️ No hay proveedores para migrar.")
            return
        
        print(f"📊 Se encontraron {total_proveedores} proveedores para migrar.")
        
        migrados = 0
        errores = 0
        
        for proveedor in proveedores:
            try:
                # Variables para verificar si hay datos que migrar
                datos_migrados = False
                
                # Migrar cedula -> identificacion_proveedor
                if hasattr(proveedor, 'cedula') and proveedor.cedula:
                    if not proveedor.identificacion_proveedor:
                        proveedor.identificacion_proveedor = proveedor.cedula
                        datos_migrados = True
                        print(f"  ✓ Migrado identificación: {proveedor.cedula}")
                
                # Migrar nombre + apellido -> razon_social_proveedor
                if hasattr(proveedor, 'nombre') and hasattr(proveedor, 'apellido'):
                    nombre_completo = ""
                    if proveedor.nombre:
                        nombre_completo += proveedor.nombre
                    if proveedor.apellido:
                        if nombre_completo:
                            nombre_completo += " " + proveedor.apellido
                        else:
                            nombre_completo = proveedor.apellido
                    
                    if nombre_completo and not proveedor.razon_social_proveedor:
                        proveedor.razon_social_proveedor = nombre_completo
                        datos_migrados = True
                        print(f"  ✓ Migrada razón social: {nombre_completo}")
                
                # Migrar nombre -> nombre_comercial_proveedor (si no existe nombre comercial)
                if hasattr(proveedor, 'nombre') and proveedor.nombre:
                    if not proveedor.nombre_comercial_proveedor:
                        proveedor.nombre_comercial_proveedor = proveedor.nombre
                        datos_migrados = True
                        print(f"  ✓ Migrado nombre comercial: {proveedor.nombre}")
                
                # Establecer valores por defecto para los nuevos campos requeridos
                if not proveedor.tipoIdentificacion:
                    # Intentar detectar el tipo basándose en la longitud de la identificación
                    if proveedor.identificacion_proveedor:
                        if len(proveedor.identificacion_proveedor) == 13:
                            proveedor.tipoIdentificacion = '04'  # RUC
                        elif len(proveedor.identificacion_proveedor) == 10:
                            proveedor.tipoIdentificacion = '05'  # Cédula
                        else:
                            proveedor.tipoIdentificacion = '06'  # Pasaporte
                    else:
                        proveedor.tipoIdentificacion = '05'  # Por defecto cédula
                    datos_migrados = True
                
                if not proveedor.tipoVenta:
                    proveedor.tipoVenta = '1'  # Por defecto: Al contado
                    datos_migrados = True
                
                if not proveedor.tipoRegimen:
                    proveedor.tipoRegimen = '1'  # Por defecto: General
                    datos_migrados = True
                
                if not proveedor.tipoProveedor:
                    proveedor.tipoProveedor = '1'  # Por defecto: Persona Natural
                    datos_migrados = True
                
                # Guardar solo si hubo cambios
                if datos_migrados:
                    proveedor.save()
                    migrados += 1
                    print(f"✅ Proveedor {proveedor.id} migrado exitosamente")
                else:
                    print(f"ℹ️ Proveedor {proveedor.id} ya está actualizado")
                    
            except Exception as e:
                errores += 1
                print(f"❌ Error migrando proveedor {proveedor.id}: {str(e)}")
                continue
        
        print(f"\n🎉 Migración completada:")
        print(f"   ✅ Migrados exitosamente: {migrados}")
        print(f"   ❌ Errores: {errores}")
        print(f"   📊 Total procesados: {total_proveedores}")
        
        if errores == 0:
            print("\n🔥 ¡Todos los proveedores fueron migrados exitosamente!")
        
    except Exception as e:
        print(f"💥 Error general en la migración: {str(e)}")

if __name__ == "__main__":
    migrar_datos_proveedor()
