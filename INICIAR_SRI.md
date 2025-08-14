# 🚀 Guía Rápida de Inicio - SRI Ecuador

## Paso 1: Instalación Inmediata

Abra su terminal y ejecute:

```bash
# Instalar dependencias
pip install zeep requests lxml cryptography

# Verificar instalación
python test_sri_integration.py
```

## Paso 2: Prueba Inmediata

### Opción A: Usar el script de ejemplo
```bash
python ejemplo_sri.py
```

### Opción B: Prueba directa con Python
```python
# Abra Python shell
python manage.py shell

# Dentro del shell:
>>> from inventario.sri.sri_client import SRIClient
>>> cliente = SRIClient(ambiente='pruebas')
>>> estado = cliente.verificar_servicio()
>>> print(estado)
```

## Paso 3: Django Management Command

```bash
# Verificar servicios SRI
python manage.py procesar_sri --diagnostico

# Procesar factura específica
python manage.py procesar_sri --factura-id 1

# Procesar todas las pendientes
python manage.py procesar_sri

# Consultar estado sin reenviar
python manage.py procesar_sri --consultar
```

## Paso 4: Integración Django

### Crear una factura de prueba:
```python
# En Django shell
from inventario.models import Factura, Cliente
from inventario.sri.integracion_django import SRIIntegration

# Crear cliente de prueba
cliente = Cliente.objects.create(
    nombre="Cliente Prueba",
    ruc="1710036156001",
    email="prueba@ejemplo.com"
)

# Crear factura
factura = Factura.objects.create(
    numero_factura="001-001-000000001",
    cliente=cliente,
    subtotal=100.00,
    iva=12.00,
    total=112.00,
    estado='PENDIENTE'
)

# Procesar con SRI
integration = SRIIntegration()
resultado = integration.procesar_factura(factura.id)
print(resultado)
```

## 📋 Comandos Rápidos

| Comando | Descripción |
|---------|-------------|
| `python test_sri_integration.py` | Prueba completa del sistema |
| `python ejemplo_sri.py` | Ejemplos interactivos |
| `python manage.py procesar_sri --diagnostico` | Verificar servicios SRI |
| `python manage.py procesar_sri --help` | Ver todas las opciones |

## 🔧 Solución de Problemas

### Si hay errores de dependencias:
```bash
pip install -r requirements.txt
```

### Si hay errores de conectividad:
1. Verificar conexión a internet
2. Verificar URLs del SRI:
   - https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantes?wsdl
   - https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantes?wsdl

### Si hay errores de certificado:
- Verificar que existe el certificado `.p12` en `media/firmas/`
- Verificar la contraseña del certificado en la configuración

## 🎯 Prueba Completa en 5 Minutos

1. **Ejecutar diagnóstico:**
   ```bash
   python test_sri_integration.py
   ```

2. **Verificar servicios:**
   ```bash
   python manage.py procesar_sri --diagnostico
   ```

3. **Ejecutar ejemplo:**
   ```bash
   python ejemplo_sri.py
   ```

4. **Procesar factura:**
   ```bash
   python manage.py procesar_sri --factura-id 1
   ```

## 📊 Resultados Esperados

✅ **Éxito**: Los servicios SRI están disponibles y responden correctamente

⚠️ **Advertencia**: Los servicios pueden estar temporalmente no disponibles (normal en horas de mantenimiento)

❌ **Error**: Verificar:
- Conexión a internet
- Dependencias instaladas
- URLs del SRI
- Certificados válidos

## 🆘 Soporte Inmediato

### Ver logs:
```bash
cat sri_test.log
tail -f logs/sri_integration.log
```

### Contacto:
- **SRI Ecuador**: 1700-SRI-SRI
- **Portal SRI**: https://www.sri.gob.ec
- **Servicios Web**: https://celcer.sri.gob.ec/comprobantes-electronicos-ws/