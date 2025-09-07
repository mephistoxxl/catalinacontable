#!/usr/bin/env python
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import *

def crear_configuracion_empresa():
    print("⚙️ CREANDO CONFIGURACIÓN GENERAL DE EMPRESA")
    print("=" * 50)
    
    # Obtener la empresa
    empresa = Empresa.objects.first()
    if not empresa:
        print("❌ No hay empresa cargada")
        return
    
    print(f"📊 Empresa encontrada: {empresa.razon_social}")
    print(f"📋 RUC: {empresa.ruc}")
    
    # Verificar si ya existe configuración
    try:
        from inventario.models import Configuracion
        
        # Eliminar configuración existente si existe
        Configuracion.objects.all().delete()
        
        # Crear nueva configuración con datos completos
        config = Configuracion.objects.create(
            empresa=empresa,
            ruc=empresa.ruc,
            razon_social=empresa.razon_social,
            nombre_comercial="MARIA SOLEDAD BOUTIQUE SD",  # Del XML de las facturas
            direccion="SANTO DOMINGO DE LOS TSACHILAS / SANTO DOMINGO / CHIGUILPE / AV. QUITO SN Y RIO YAMBOYA",  # Del XML
            telefono="0991116753",  # Del XML
            email="linapumalpa3@gmail.com",  # Del XML
            obligado_contabilidad=False,  # Del XML dice "NO"
            agente_retencion=False,
            contribuyente_especial="",
            
            # Configuraciones adicionales de facturación electrónica
            ambiente_facturacion="2",  # Producción (del XML)
            tipo_emision="1",  # Normal
            establecimiento="002",  # Del backup
            punto_emision="999",  # Del backup
            
            # Logo y configuración visual
            logo="",
            mostrar_logo=True,
            pie_pagina="Gracias por su preferencia",
            
            # Configuraciones SRI
            clave_certificado="",
            archivo_certificado="",
            validar_sri=True,
            generar_ride=True,
            
            # Configuración de impresión
            formato_impresion="A4",
            copias_factura=1,
            mostrar_precios_con_iva=True,
            
            # Configuración de negocio
            manejo_inventario=True,
            permitir_facturas_sin_stock=False,
            descuento_maximo=10.00,
            
            # Información bancaria
            banco_principal="",
            numero_cuenta="",
            tipo_cuenta="",
            
            # Configuración de reportes
            moneda_sistema="USD",
            separador_miles=",",
            separador_decimales=".",
            decimales_precios=2,
            
            # Configuración de seguridad
            inactividad_session=30,
            backup_automatico=True,
            frecuencia_backup=7,
            
            # Información adicional
            sitio_web="",
            facebook="",
            instagram="",
            whatsapp="0991116753",
            
            # Configuración de impuestos
            porcentaje_iva=15.00,  # Del XML vemos 15%
            codigo_iva="4",  # Del XML
            
            # Estado
            activo=True
        )
        
        print("✅ Configuración creada exitosamente!")
        print(f"📋 Razón Social: {config.razon_social}")
        print(f"📍 Dirección: {config.direccion}")
        print(f"📞 Teléfono: {config.telefono}")
        print(f"📧 Email: {config.email}")
        print(f"🏢 Nombre Comercial: {config.nombre_comercial}")
        print(f"🌍 Ambiente: {'Producción' if config.ambiente_facturacion == '2' else 'Pruebas'}")
        print(f"🏪 Establecimiento: {config.establecimiento}")
        print(f"📍 Punto Emisión: {config.punto_emision}")
        
    except ImportError:
        print("❌ El modelo Configuracion no existe")
        print("ℹ️ Esto es normal si no tienes ese modelo en tu sistema")
    except Exception as e:
        print(f"❌ Error creando configuración: {e}")
        print("ℹ️ Intentando crear configuración básica...")
        
        # Intentar otros métodos de configuración
        try:
            # Buscar otros modelos de configuración
            from django.apps import apps
            models = apps.get_models()
            config_models = [m for m in models if 'config' in m.__name__.lower()]
            
            print("📋 Modelos de configuración disponibles:")
            for model in config_models:
                print(f"  • {model.__name__}")
                
        except Exception as e2:
            print(f"❌ Error buscando modelos: {e2}")
    
    print("\n🎯 CONFIGURACIÓN COMPLETADA")

if __name__ == "__main__":
    crear_configuracion_empresa()
