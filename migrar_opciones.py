#!/usr/bin/env python
import os
import django
import json
from decimal import Decimal
from datetime import datetime
from django.utils import timezone

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import *

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
    except:
        return None

def migrar_opciones():
    print("⚙️ MIGRACIÓN DE CONFIGURACIÓN GENERAL")
    print("====================================")
    
    # Cargar backup
    with open('backup_sqlite_data.json', 'r') as f:
        backup_data = json.load(f)
    
    # Obtener empresa existente
    empresa = Empresa.objects.first()
    if not empresa:
        print("❌ No hay empresa configurada")
        return
    
    print(f"✅ Empresa encontrada: {empresa.razon_social}")
    
    # Verificar opciones existentes
    opciones_existentes = Opciones.objects.count()
    print(f"📊 Configuraciones existentes: {opciones_existentes}")
    
    # Limpiar opciones existentes
    if opciones_existentes > 0:
        print("🗑️ Limpiando configuraciones existentes...")
        Opciones.objects.all().delete()
    
    # CARGAR CONFIGURACIÓN GENERAL (OPCIONES)
    print("\n⚙️ Cargando configuración general...")
    opciones_data = [item for item in backup_data if item['model'] == 'inventario.opciones']
    
    if not opciones_data:
        print("❌ No se encontraron datos de configuración en el backup")
        return
    
    for item in opciones_data:
        fields = item['fields']
        opciones = Opciones.objects.create(
            empresa=empresa,
            identificacion=fields.get('identificacion', '0000000000000'),
            # firma_electronica=fields.get('firma_electronica', ''),  # Omitir por ahora
            # password_firma=fields.get('password_firma', ''),  # Omitir por ahora
            fecha_caducidad_firma=parse_date(fields.get('fecha_caducidad_firma')),
            razon_social=fields.get('razon_social', '[CONFIGURAR RAZÓN SOCIAL]'),
            nombre_comercial=fields.get('nombre_comercial', '[CONFIGURAR NOMBRE COMERCIAL]'),
            direccion_establecimiento=fields.get('direccion_establecimiento', '[CONFIGURAR DIRECCIÓN]'),
            correo=fields.get('correo', 'configurar@empresa.com'),
            telefono=fields.get('telefono', '0000000000'),
            obligado=fields.get('obligado', 'SI'),
            tipo_regimen=fields.get('tipo_regimen', 'GENERAL'),
            es_contribuyente_especial=fields.get('es_contribuyente_especial', False),
            numero_contribuyente_especial=fields.get('numero_contribuyente_especial'),
            imagen=fields.get('imagen', ''),
            es_agente_retencion=fields.get('es_agente_retencion', False),
            numero_agente_retencion=fields.get('numero_agente_retencion'),
            valor_iva=int(fields.get('valor_iva', 15)),
            moneda=fields.get('moneda', 'USD'),
            nombre_negocio=fields.get('nombre_negocio', 'Mi Negocio'),
            mensaje_factura=fields.get('mensaje_factura', 'Gracias por su compra'),
            tipo_ambiente=fields.get('tipo_ambiente', '1'),
            tipo_emision=fields.get('tipo_emision', '1')
        )
        print(f"✅ Configuración migrada:")
        print(f"   - Empresa: {opciones.razon_social}")
        print(f"   - RUC: {opciones.identificacion}")
        print(f"   - Correo: {opciones.correo}")
        print(f"   - Teléfono: {opciones.telefono}")
        print(f"   - Ambiente: {opciones.ambiente_descripcion}")
        print(f"   - IVA: {opciones.valor_iva}%")
    
    print("\n🎉 ¡Configuración general migrada exitosamente!")

if __name__ == "__main__":
    migrar_opciones()
