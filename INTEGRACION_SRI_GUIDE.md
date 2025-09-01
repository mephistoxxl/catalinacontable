# Guía de Integración SRI - Sistema de Facturación Electrónica Ecuador

Esta guía proporciona instrucciones completas para implementar la integración con el Servicio de Rentas Internas (SRI) de Ecuador para facturación electrónica.

## 📋 Tabla de Contenidos

1. [Requisitos Previos](#requisitos-previos)
2. [Instalación](#instalación)
3. [Configuración](#configuración)
4. [Uso del Sistema](#uso-del-sistema)
5. [Estructura de Archivos](#estructura-de-archivos)
6. [Ejemplos de Uso](#ejemplos-de-uso)
7. [Manejo de Errores](#manejo-de-errores)
8. [Solución de Problemas](#solución-de-problemas)

## 🔧 Requisitos Previos

### Dependencias del Sistema

```bash
# Instalar dependencias Python
pip install -r requirements.txt

# Dependencias específicas SRI
pip install zeep>=4.2.1
pip install requests>=2.31.0
pip install lxml>=4.9.3
```

### Certificados y Credenciales

1. **Certificado Digital**: Archivo `.p12` con firma electrónica
2. **Contraseña del Certificado**: Proporcionada por la entidad certificadora
3. **RUC de la Empresa**: Para generar claves de acceso

## ⚙️ Configuración

### 1. Configuración Django

El ambiente (pruebas/producción) se define desde el formulario de Firma Electrónica y se almacena en `Opciones.tipo_ambiente`.
Agregar en `settings.py`:

```python
# Configuración SRI
SRI_TIMEOUT = 30  # segundos

# URLs de los servicios SRI
SRI_WSDL_RECEPCION_PRUEBAS = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantes?wsdl"
SRI_WSDL_AUTORIZACION_PRUEBAS = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantes?wsdl"

SRI_WSDL_RECEPCION_PRODUCCION = "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantes?wsdl"
SRI_WSDL_AUTORIZACION_PRODUCCION = "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantes?wsdl"

# Configuración de almacenamiento
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Configuración de logs
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'sri_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/sri_integration.log',
        },
    },
    'loggers': {
        'inventario.sri': {
            'handlers': ['sri_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### 2. Configuración de Modelos

Asegúrese de que los modelos tengan los campos necesarios:

```python
# En models.py
class Factura(models.Model):
    numero_factura = models.CharField(max_length=50, unique=True)
    clave_acceso = models.CharField(max_length=49, blank=True, null=True)
    numero_autorizacion = models.CharField(max_length=50, blank=True, null=True)
    fecha_autorizacion = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(max_length=20, default='PENDIENTE')
    mensaje_sri = models.TextField(blank=True, null=True)
    mensaje_sri_detalle = models.TextField(blank=True, null=True)
    ride_autorizado = models.FileField(upload_to='rides/', blank=True, null=True)
    xml_enviado = models.TextField(blank=True, null=True)
    # ... otros campos
```

## 🚀 Uso del Sistema

### 1. Cliente SRI Básico

```python
from inventario.sri.sri_client import SRIClient

# Crear cliente
cliente = SRIClient(ambiente='pruebas')  # o 'produccion'

# Verificar servicios
estado = cliente.verificar_servicio()
print("Servicios disponibles:", estado)

# Enviar comprobante
xml_content = "...XML del comprobante..."
clave_acceso = "...clave de acceso..."
resultado = cliente.enviar_comprobante(xml_content, clave_acceso)

# Consultar autorización
resultado_autorizacion = cliente.consultar_autorizacion(clave_acceso)

# Proceso completo
resultado_completo = cliente.procesar_comprobante_completo(
    xml_content, 
    clave_acceso,
    max_intentos=3,
    espera_segundos=2
)
```

### 2. Integración Django

```python
from inventario.sri.integracion_django import SRIIntegration

# Procesar factura completa
integration = SRIIntegration()
resultado = integration.procesar_factura(factura_id=123)

# Consultar estado
estado = integration.consultar_estado_factura(factura_id=123)

# Reenviar factura rechazada
resultado_reenvio = integration.reenviar_factura(factura_id=123)
```

### 3. Django Admin Integration

```python
# admin.py
from django.contrib import admin
from inventario.models import Factura
from inventario.sri.integracion_django import SRIIntegration

@admin.action(description='Enviar al SRI')
def enviar_sri(modeladmin, request, queryset):
    integration = SRIIntegration()
    for factura in queryset:
        resultado = integration.procesar_factura(factura.id)
        if resultado['success']:
            modeladmin.message_user(request, f"Factura {factura.numero_factura} procesada")
        else:
            modeladmin.message_user(request, f"Error: {resultado['message']}", level='error')

@admin.action(description='Consultar estado SRI')
def consultar_estado_sri(modeladmin, request, queryset):
    integration = SRIIntegration()
    for factura in queryset:
        resultado = integration.consultar_estado_factura(factura.id)
        if resultado['success']:
            modeladmin.message_user(request, f"Estado actualizado para {factura.numero_factura}")

class FacturaAdmin(admin.ModelAdmin):
    actions = [enviar_sri, consultar_estado_sri]
    list_display = ['numero_factura', 'estado', 'clave_acceso', 'fecha_creacion']
    list_filter = ['estado', 'fecha_creacion']
    search_fields = ['numero_factura', 'clave_acceso']
```

### 4. Django Views

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from inventario.sri.integracion_django import SRIIntegration
import json

@csrf_exempt
def procesar_factura_api(request, factura_id):
    """API endpoint para procesar facturas"""
    if request.method == 'POST':
        try:
            integration = SRIIntegration()
            resultado = integration.procesar_factura(factura_id)
            return JsonResponse(resultado)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@csrf_exempt
def consultar_estado_api(request, factura_id):
    """API endpoint para consultar estado"""
    if request.method == 'GET':
        try:
            integration = SRIIntegration()
            resultado = integration.consultar_estado_factura(factura_id)
            return JsonResponse(resultado)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)
```

## 📁 Estructura de Archivos

```
inventario/
├── sri/
│   ├── __init__.py
│   ├── sri_client.py          # Cliente principal SOAP
│   ├── integracion_django.py # Integración con Django
│   ├── xml_generator.py       # Generador de XML (por implementar)
│   ├── pdf_firmador.py        # Firmador de PDFs
│   └── ride_generator.py      # Generador de RIDE
├── models.py
├── views.py
├── admin.py
├── urls.py
templates/
├── rides/
├── xml/
└── logs/
```

## 📝 Ejemplos de Uso

### Ejemplo 1: Procesar Factura Individual

```python
# Crear una factura y procesarla
from inventario.models import Factura, Cliente, Producto
from inventario.sri.integracion_django import SRIIntegration

# Crear factura
cliente = Cliente.objects.get(id=1)
factura = Factura.objects.create(
    cliente=cliente,
    numero_factura="001-001-000000001",
    fecha=datetime.now(),
    subtotal=100.00,
    iva=12.00,
    total=112.00,
    estado='PENDIENTE'
)

# Agregar detalles
DetalleFactura.objects.create(
    factura=factura,
    producto=Producto.objects.get(id=1),
    cantidad=1,
    precio_unitario=100.00,
    subtotal=100.00
)

# Procesar con SRI
integration = SRIIntegration()
resultado = integration.procesar_factura(factura.id)

if resultado['success']:
    print("Factura procesada exitosamente")
    print(f"Clave de acceso: {resultado['clave_acceso']}")
    print(f"Estado: {resultado['resultado']['estado']}")
else:
    print(f"Error: {resultado['message']}")
```

### Ejemplo 2: Procesar Lote de Facturas

```python
# Procesar todas las facturas pendientes
from inventario.models import Factura
from inventario.sri.integracion_django import SRIIntegration

integration = SRIIntegration()
facturas_pendientes = Factura.objects.filter(estado='PENDIENTE')

for factura in facturas_pendientes:
    resultado = integration.procesar_factura(factura.id)
    print(f"Factura {factura.numero_factura}: {resultado}")
```

### Ejemplo 3: Manejo de Respuestas

```python
# Interpretar resultados del SRI
resultado = cliente.procesar_comprobante_completo(xml_content, clave_acceso)

if resultado['estado'] == 'AUTORIZADO':
    autorizacion = resultado['autorizaciones'][0]
    print(f"✅ Autorizado - Número: {autorizacion['numeroAutorizacion']}")
    print(f"📅 Fecha: {autorizacion['fechaAutorizacion']}")
    
elif resultado['estado'] == 'NO AUTORIZADO':
    print("❌ No autorizado")
    for msg in resultado['mensajes']:
        print(f"   - {msg['identificador']}: {msg['mensaje']}")
        
elif resultado['estado'] == 'RECIBIDA':
    print("⏳ Recibida, esperando autorización")
    
else:
    print(f"⚠️ Estado: {resultado['estado']}")
```

## ⚠️ Manejo de Errores

### Errores Comunes y Soluciones

| Error | Causa | Solución |
|-------|-------|----------|
| `SOAP_ERROR` | Problema con el servicio SOAP | Verificar conectividad y URLs |
| `CERTIFICATE_ERROR` | Certificado no válido | Verificar certificado y contraseña |
| `CLAVE_ACCESO_INVALIDA` | Clave mal formada | Validar formato de clave |
| `TIMEOUT` | Servicio SRI lento | Aumentar timeout o reintentar |
| `XML_INVALIDO` | XML mal formado | Validar XML contra XSD |

### Implementación de Reintentos

```python
# Configurar reintentos automáticos
resultado = cliente.procesar_comprobante_completo(
    xml_content, 
    clave_acceso,
    max_intentos=5,      # Más intentos
    espera_segundos=5    # Mayor espera
)
```

### Logging Detallado

```python
import logging

# Configurar logger específico para SRI
logger = logging.getLogger('inventario.sri')
logger.setLevel(logging.DEBUG)

# Handler para archivo
handler = logging.FileHandler('logs/sri_debug.log')
handler.setLevel(logging.DEBUG)

# Formato detallado
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)
```

## 🔍 Solución de Problemas

### Verificar Servicios SRI

```python
# Script de diagnóstico
from inventario.sri.sri_client import SRIClient

def diagnosticar_sri():
    cliente = SRIClient(ambiente='pruebas')
    estado = cliente.verificar_servicio()
    
    print("Diagnóstico SRI:")
    print(f"  Recepción: {'✅ OK' if estado['recepcion']['disponible'] else '❌ Error'}")
    print(f"  Autorización: {'✅ OK' if estado['autorizacion']['disponible'] else '❌ Error'}")
    
    if estado['recepcion']['error']:
        print(f"  Error recepción: {estado['recepcion']['error']}")
    if estado['autorizacion']['error']:
        print(f"  Error autorización: {estado['autorizacion']['error']}")

# Ejecutar diagnóstico
diagnosticar_sri()
```

### Validar XML

```python
# Validar XML contra esquema XSD
import xmlschema

def validar_xml(xml_content):
    try:
        schema = xmlschema.XMLSchema('factura_v1.1.0.xsd')
        schema.validate(xml_content)
        return True, "XML válido"
    except xmlschema.XMLSchemaValidationError as e:
        return False, str(e)
```

### Monitoreo de Estado

```python
# Script para monitoreo continuo
import time
from datetime import datetime

def monitorear_facturas():
    integration = SRIIntegration()
    
    while True:
        print(f"[{datetime.now()}] Monitoreando facturas...")
        
        # Consultar facturas pendientes
        resultados = integration.consultar_lote_facturas()
        
        for res in resultados:
            factura = res['factura']
            estado = res['resultado']['estado']
            print(f"  Factura {factura.numero_factura}: {estado}")
        
        time.sleep(300)  # Verificar cada 5 minutos
```

## 📊 Métricas y Reportes

### Generar Reporte de Facturas

```python
def generar_reporte_facturas(fecha_inicio, fecha_fin):
    from inventario.models import Factura
    
    facturas = Factura.objects.filter(
        fecha__range=[fecha_inicio, fecha_fin]
    )
    
    reporte = {
        'total': facturas.count(),
        'autorizadas': facturas.filter(estado='AUTORIZADO').count(),
        'rechazadas': facturas.filter(estado='RECHAZADO').count(),
        'pendientes': facturas.filter(estado='PENDIENTE').count(),
        'errores': facturas.filter(estado='ERROR').count(),
    }
    
    return reporte
```

## 🔄 Mantenimiento

### Actualización de Certificados

1. **Antes de vencimiento**: Configurar alertas 30 días antes
2. **Proceso de renovación**:
   - Obtener nuevo certificado
   - Actualizar en configuración
   - Probar en ambiente de pruebas
   - Desplegar en producción

### Actualización de URLs SRI

Las URLs del SRI pueden cambiar. Mantener actualizado:

```python
# Verificar URLs actuales
import requests

def verificar_urls_sri():
    urls = [
        "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantes?wsdl",
        "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantes?wsdl"
    ]
    
    for url in urls:
        try:
            response = requests.get(url, timeout=10)
            print(f"✅ {url}: {response.status_code}")
        except Exception as e:
            print(f"❌ {url}: {e}")
```

## 🆘 Soporte

Para soporte técnico:

1. **Verificar logs**: `logs/sri_integration.log`
2. **Ejecutar diagnóstico**: Usar script de diagnóstico
3. **Validar XML**: Asegurar XML válido
4. **Verificar certificado**: Comprobar validez y contraseña
5. **Contactar SRI**: Para problemas con servicios

### Contacto SRI

- **Portal SRI**: https://www.sri.gob.ec
- **Servicio al contribuyente**: 1700-SRI-SRI
- **Correo**: servicioalcliente@sri.gob.ec