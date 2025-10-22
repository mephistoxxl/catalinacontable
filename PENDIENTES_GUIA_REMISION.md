# 📋 LISTA COMPLETA - Pendientes para Guía de Remisión

## ✅ COMPLETADO (Lo que YA funciona):

1. ✅ **Base de datos** - Modelos creados y migrados
   - GuiaRemision
   - Transportista
   - DestinatarioGuia
   - DetalleDestinatarioGuia
   - DetalleGuiaRemision

2. ✅ **Formulario HTML** - Ultra-compacto y funcional
   - emitirGuiaRemision.html
   - Búsqueda de transportista con API
   - Búsqueda de destinatarios con API
   - Tabla dinámica de destinatarios

3. ✅ **Archivos del SRI** - Esquemas oficiales
   - GuiaRemision_V1.1.0.xsd
   - GuiaRemision_V1.1.0.xml (ejemplo)

4. ✅ **Módulos de procesamiento** - Listos para usar
   - xml_generator_guia.py
   - firmador_guia.py
   - integracion_sri_guia.py

---

## ❌ PENDIENTES (Lo que falta implementar):

### 1. **Vista emitir_guia_remision** (PRIORIDAD ALTA)
**Archivo:** `inventario/guia_remision/views.py`

**Falta:**
- [ ] Actualizar vista POST para procesar destinatarios desde la tabla HTML
- [ ] Guardar múltiples destinatarios (DestinatarioGuia)
- [ ] Guardar detalles de productos por destinatario (DetalleDestinatarioGuia)
- [ ] Integrar con `IntegracionGuiaRemisionSRI` para:
  - Generar clave de acceso
  - Generar XML
  - Firmar XML
  - Enviar al SRI
  - Consultar autorización

**Código necesario:**
```python
from .integracion_sri_guia import IntegracionGuiaRemisionSRI

def emitir_guia_remision(request):
    if request.method == 'POST':
        # 1. Crear GuiaRemision con datos del formulario
        # 2. Procesar array destinatarios[] desde POST
        # 3. Crear DestinatarioGuia para cada uno
        # 4. Llamar IntegracionGuiaRemisionSRI.procesar_guia_remision()
        # 5. Redirigir a ver_guia con mensaje de éxito/error
```

---

### 2. **Modelo Secuencia para Guías** (PRIORIDAD ALTA)
**Archivo:** `inventario/models.py`

**Falta:**
- [ ] Crear modelo `SecuenciaGuia` (similar a SecuenciaFactura)
- [ ] Campos: descripcion, establecimiento, punto_emision, secuencial_actual, activo
- [ ] Vista GET para `/inventario/guia-remision/obtener_datos_secuencia/<id>/`

**Código necesario:**
```python
class SecuenciaGuia(models.Model):
    empresa = models.ForeignKey('Empresa', on_delete=models.CASCADE)
    descripcion = models.CharField(max_length=200)
    establecimiento = models.CharField(max_length=3, default='001')
    punto_emision = models.CharField(max_length=3, default='001')
    secuencial_actual = models.CharField(max_length=9, default='000000001')
    activo = models.BooleanField(default=True)
```

---

### 3. **URLs y Rutas** (PRIORIDAD ALTA)
**Archivo:** `inventario/guia_remision/urls.py`

**Falta:**
- [ ] Ruta para `emitir_guia_remision`
- [ ] Ruta para `obtener_datos_secuencia/<id>/`
- [ ] Incluir urls en `inventario/urls.py`

**Código necesario:**
```python
urlpatterns = [
    path('emitir/', views.emitir_guia_remision, name='emitir_guia_remision'),
    path('obtener_datos_secuencia/<int:secuencia_id>/', views.obtener_datos_secuencia, name='obtener_datos_secuencia_guia'),
    path('listar/', views.listar_guias_remision, name='listar_guias_remision'),
]
```

---

### 4. **Actualizar XML Generator** (PRIORIDAD MEDIA)
**Archivo:** `inventario/guia_remision/xml_generator_guia.py`

**Falta:**
- [ ] Actualizar `_generar_destinatarios()` para usar modelo `DestinatarioGuia`
- [ ] Incluir detalles de productos por destinatario
- [ ] Validar contra XSD antes de retornar
- [ ] Agregar campos opcionales del XSD:
  - dirEstablecimiento
  - rise
  - agenteRetencion
  - contribuyenteRimpe
  - camposAdicionales

**Estructura XML correcta:**
```xml
<destinatarios>
  <destinatario>
    <identificacionDestinatario>1234567890001</identificacionDestinatario>
    <razonSocialDestinatario>CLIENTE S.A.</razonSocialDestinatario>
    <dirDestinatario>Dirección completa</dirDestinatario>
    <motivoTraslado>VENTA</motivoTraslado>
    <codDocSustento>01</codDocSustento>
    <numDocSustento>001-001-000000123</numDocSustento>
    <detalles>
      <detalle>
        <codigoInterno>PROD001</codigoInterno>
        <descripcion>Producto XYZ</descripcion>
        <cantidad>10.000000</cantidad>
      </detalle>
    </detalles>
  </destinatario>
</destinatarios>
```

---

### 5. **Template de Lista** (PRIORIDAD BAJA)
**Archivo:** `inventario/templates/inventario/guia_remision/listarGuiasRemision.html`

**Falta:**
- [ ] Crear template con tabla de guías
- [ ] Botones: Buscar, Nueva, Ver, Editar, Anular, Descargar PDF
- [ ] Filtros por: número, cliente, fecha, estado
- [ ] Paginación

---

### 6. **Template de Visualización** (PRIORIDAD BAJA)
**Archivo:** `inventario/templates/inventario/guia_remision/verGuiaRemision.html`

**Falta:**
- [ ] Mostrar todos los datos de la guía
- [ ] Lista de destinatarios con sus detalles
- [ ] Botones de acción según estado
- [ ] Mostrar XML si está autorizado

---

### 7. **Validación de Campos** (PRIORIDAD MEDIA)
**Frontend (JavaScript):**
- [ ] Validar RUC formato ecuatoriano
- [ ] Validar al menos 1 destinatario
- [ ] Validar fechas (inicio < fin)
- [ ] Validar placa formato válido

**Backend (Django):**
- [ ] Validar campos obligatorios
- [ ] Validar unicidad de clave_acceso
- [ ] Validar secuencial no repetido

---

### 8. **Manejo de Errores** (PRIORIDAD MEDIA)
**Falta:**
- [ ] Try-catch en vista emitir
- [ ] Logging de errores
- [ ] Mensajes amigables al usuario
- [ ] Rollback de transacción si falla SRI

---

### 9. **Testing** (PRIORIDAD BAJA)
**Falta:**
- [ ] Test de generación de XML
- [ ] Test de firma XML
- [ ] Test de clave de acceso
- [ ] Test de validación contra XSD
- [ ] Test de envío al SRI (modo pruebas)

---

## 🚀 ORDEN DE IMPLEMENTACIÓN RECOMENDADO:

### **Fase 1 - Funcionalidad Básica (1-2 horas)**
1. Crear modelo `SecuenciaGuia` + migración
2. Actualizar vista `emitir_guia_remision` para procesar POST
3. Configurar URLs correctamente
4. Probar guardado en base de datos

### **Fase 2 - Integración SRI (2-3 horas)**
5. Actualizar `xml_generator_guia.py` con destinatarios reales
6. Probar generación de XML
7. Probar firma de XML
8. Validar XML contra XSD

### **Fase 3 - Conexión con SRI (1-2 horas)**
9. Integrar `IntegracionGuiaRemisionSRI` en vista
10. Probar envío a SRI ambiente pruebas
11. Probar consulta de autorización
12. Manejar respuestas del SRI

### **Fase 4 - Finalización (2-3 horas)**
13. Crear template de lista
14. Crear template de visualización
15. Agregar validaciones frontend/backend
16. Testing completo

---

## 📝 NOTAS IMPORTANTES:

1. **NO tocar archivos de factura** - Todo es independiente
2. **Usar el mismo SRIClient** - Ya funciona para todos los documentos
3. **Validar contra XSD** - Usar lxml para validación automática
4. **Ambiente pruebas primero** - No probar en producción
5. **Logs detallados** - Para debugging

---

## 🔥 PRÓXIMO PASO INMEDIATO:

**Crear vista `emitir_guia_remision` funcional que:**
1. Reciba datos del formulario
2. Cree GuiaRemision + Destinatarios + Detalles
3. Llame a IntegracionGuiaRemisionSRI
4. Retorne resultado al usuario

**¿Empezamos con esto?**
