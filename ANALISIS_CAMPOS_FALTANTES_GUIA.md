# 🔍 ANÁLISIS COMPLETO: Campos Faltantes en Guía de Remisión vs XSD del SRI

## ✅ CAMPOS QUE YA TENEMOS (Correctos)

### En GuiaRemision (modelo principal):
- ✅ `establecimiento` (3 dígitos)
- ✅ `punto_emision` (3 dígitos)
- ✅ `secuencial` (9 dígitos)
- ✅ `transportista_ruc` → **rucTransportista**
- ✅ `transportista_nombre` → **razonSocialTransportista**
- ✅ `direccion_partida` → **dirPartida**
- ✅ `fecha_inicio_traslado` → **fechaIniTransporte**
- ✅ `fecha_fin_traslado` → **fechaFinTransporte**
- ✅ `placa` → **placa**
- ✅ `ruta` (aunque se usa más en destinatarios)
- ✅ `clave_acceso` (49 dígitos)

### En DestinatarioGuia:
- ✅ `identificacion_destinatario` → **identificacionDestinatario**
- ✅ `razon_social_destinatario` → **razonSocialDestinatario**
- ✅ `dir_destinatario` → **dirDestinatario**
- ✅ `motivo_traslado` → **motivoTraslado**
- ✅ `cod_doc_sustento` → **codDocSustento**
- ✅ `num_doc_sustento` → **numDocSustento**
- ✅ `num_aut_doc_sustento` → **numAutDocSustento**
- ✅ `fecha_emision_doc_sustento` → **fechaEmisionDocSustento**
- ✅ `doc_aduanero_unico` → **docAduaneroUnico**
- ✅ `cod_estab_destino` → **codEstabDestino**
- ✅ `ruta` → **ruta**

### En DetalleDestinatarioGuia:
- ✅ `codigo_interno` → **codigoInterno**
- ✅ `descripcion` → **descripcion**
- ✅ `cantidad` → **cantidad**

---

## ❌ CAMPOS FALTANTES CRÍTICOS (Requeridos por XSD)

### 1. **infoGuiaRemision** (Sección completa)

#### En GuiaRemision Model:
```python
# FALTA:
tipo_identificacion_transportista = models.CharField(
    max_length=2,
    choices=[
        ('04', 'RUC'),
        ('05', 'Cédula'),
        ('06', 'Pasaporte'),
        ('07', 'Consumidor Final'),
        ('08', 'Identificación del exterior'),
    ],
    default='05',
    help_text='Tipo de identificación del transportista'
)

dir_establecimiento = models.CharField(
    max_length=300,
    blank=True,
    help_text='Dirección del establecimiento emisor'
)

# Campos opcionales pero importantes:
rise = models.CharField(
    max_length=40,
    blank=True,
    help_text='Régimen RISE del transportista'
)

obligado_contabilidad = models.CharField(
    max_length=2,
    choices=[('SI', 'SI'), ('NO', 'NO')],
    blank=True,
    help_text='Obligado a llevar contabilidad'
)

contribuyente_especial = models.CharField(
    max_length=13,
    blank=True,
    help_text='Número de contribuyente especial'
)
```

#### En Empresa Model (para infoTributaria):
```python
# VERIFICAR QUE EXISTAN:
- razon_social ✅ (Ya existe)
- ruc ✅ (Ya existe)
- nombre_comercial ❌ (Puede que falte)
- dir_matriz ❌ (Dirección matriz)
- agente_retencion ❌ (Resolución)
- contribuyente_rimpe ❌ (Si aplica)
```

### 2. **Campos en el Formulario HTML**

#### AGREGAR al formulario `emitirGuiaRemision.html`:

```html
<!-- En sección "Datos de Transporte" -->
<div class="form-group">
  <label>Tipo Identificación Transportista</label>
  <select name="tipo_identificacion_transportista" class="form-control" required>
    <option value="05" selected>Cédula</option>
    <option value="04">RUC</option>
    <option value="06">Pasaporte</option>
    <option value="08">Identificación del exterior</option>
  </select>
</div>

<!-- OPCIONAL: Campos adicionales del transportista -->
<div class="form-group">
  <label>RISE (Opcional)</label>
  <input type="text" name="rise" class="form-control" maxlength="40">
</div>

<div class="form-group">
  <label>Obligado Contabilidad</label>
  <select name="obligado_contabilidad" class="form-control">
    <option value="">N/A</option>
    <option value="SI">SI</option>
    <option value="NO">NO</option>
  </select>
</div>

<div class="form-group">
  <label>Contribuyente Especial (Opcional)</label>
  <input type="text" name="contribuyente_especial" class="form-control" maxlength="13">
</div>
```

#### AGREGAR en tabla de Destinatarios (columnas opcionales):

```html
<!-- Ya tienes estas columnas visibles:
- RUC
- Destinatario
- Dirección
- Motivo
- Documento
-->

<!-- AGREGAR columnas ocultas/colapsadas para campos opcionales: -->
<th style="display:none;">Doc. Aduanero</th>
<th style="display:none;">Cod. Estab.</th>
<th style="display:none;">Num. Aut.</th>
<th style="display:none;">Fecha Doc.</th>

<!-- Y en cada fila: -->
<td style="display:none;">
  <input type="text" name="destinatarios[${i}][doc_aduanero]" 
         class="form-control" maxlength="20">
</td>
<td style="display:none;">
  <input type="text" name="destinatarios[${i}][cod_estab]" 
         class="form-control" maxlength="3" value="001">
</td>
<td style="display:none;">
  <input type="text" name="destinatarios[${i}][num_aut]" 
         class="form-control" maxlength="49">
</td>
<td style="display:none;">
  <input type="date" name="destinatarios[${i}][fecha_doc]" 
         class="form-control">
</td>
```

### 3. **Campos en DetalleDestinatarioGuia**

```python
# FALTA:
codigo_adicional = models.CharField(
    max_length=25,
    blank=True,
    help_text='Código adicional del producto'
)

# Para detallesAdicionales (hasta 3):
# Opción 1: Usar JSONField
detalles_adicionales = models.JSONField(
    blank=True,
    default=dict,
    help_text='Detalles adicionales del producto (max 3)'
)

# Opción 2: Crear modelo separado (más normalizado)
class DetalleAdicionalProducto(models.Model):
    detalle = models.ForeignKey(DetalleDestinatarioGuia, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=300)
    valor = models.CharField(max_length=300)
```

### 4. **En views_nuevas.py** (Procesamiento POST)

```python
# AGREGAR en emitir_guia_remision_nueva():
guia = GuiaRemision(
    # ... campos existentes ...
    tipo_identificacion_transportista=request.POST.get('tipo_identificacion_transportista', '05'),
    dir_establecimiento=empresa.direccion,  # Desde empresa
    rise=request.POST.get('rise', ''),
    obligado_contabilidad=request.POST.get('obligado_contabilidad', ''),
    contribuyente_especial=request.POST.get('contribuyente_especial', ''),
)

# En _extraer_destinatarios_del_post():
destinatario_data = {
    # ... campos existentes ...
    'doc_aduanero': request.POST.get(f'destinatarios[{i}][doc_aduanero]', ''),
    'cod_estab': request.POST.get(f'destinatarios[{i}][cod_estab]', '001'),
    'num_aut': request.POST.get(f'destinatarios[{i}][num_aut]', ''),
    'fecha_doc': request.POST.get(f'destinatarios[{i}][fecha_doc]', None),
}
```

---

## 🎯 PRIORIDAD DE IMPLEMENTACIÓN

### **🔴 CRÍTICO (Sin esto el SRI rechazará):**
1. ✅ `tipo_identificacion_transportista` - **FALTA EN MODELO Y FORM**
2. ✅ Información tributaria completa (empresa)
3. ✅ Destinatarios con campos mínimos (ya tenemos)
4. ✅ Detalles de productos (ya tenemos)

### **🟡 IMPORTANTE (Mejorar validación):**
1. ✅ `dir_establecimiento` - Dirección del punto de emisión
2. ✅ `obligado_contabilidad` - Si la empresa lleva contabilidad
3. ✅ `contribuyente_especial` - Si aplica

### **🟢 OPCIONAL (No bloquea autorización):**
1. ⚪ `rise` - Solo si el transportista está en RISE
2. ⚪ `doc_aduanero_unico` - Solo para importaciones
3. ⚪ `cod_estab_destino` - Si hay múltiples bodegas
4. ⚪ `codigo_adicional` - Código de barras/PLU
5. ⚪ `detalles_adicionales` - Info extra de productos
6. ⚪ `maquinaFiscal` - Solo si se usa

---

## 📝 CAMPOS EN INFORMACIÓN ADICIONAL

El XSD permite hasta **15 campos adicionales** opcionales:
```xml
<infoAdicional>
    <campoAdicional nombre="EMAIL">cliente@email.com</campoAdicional>
    <campoAdicional nombre="TELEFONO">0991234567</campoAdicional>
    <campoAdicional nombre="OBSERVACIONES">Entregar en horario de oficina</campoAdicional>
</infoAdicional>
```

**Ya tenemos:** Campo `informacion_adicional` (TextField) que podemos parsear.

**Sugerencia:** Cambiar a JSONField para estructurar mejor:
```python
informacion_adicional = models.JSONField(
    blank=True,
    default=list,
    help_text='Campos adicionales (max 15)'
)
# Ejemplo: [{"nombre": "EMAIL", "valor": "test@email.com"}]
```

---

## 🔧 RESUMEN DE CAMBIOS NECESARIOS

### **Archivo 1: `inventario/models.py` (GuiaRemision)**
```python
# AGREGAR 5 campos nuevos:
tipo_identificacion_transportista = CharField(max_length=2, default='05')
dir_establecimiento = CharField(max_length=300, blank=True)
rise = CharField(max_length=40, blank=True)
obligado_contabilidad = CharField(max_length=2, blank=True)
contribuyente_especial = CharField(max_length=13, blank=True)
```

### **Archivo 2: `inventario/models.py` (DetalleDestinatarioGuia)**
```python
# AGREGAR:
codigo_adicional = CharField(max_length=25, blank=True)
```

### **Archivo 3: `emitirGuiaRemision.html`**
```html
<!-- AGREGAR después del campo transportista_ruc: -->
<div class="form-group">
  <label>Tipo Identificación</label>
  <select name="tipo_identificacion_transportista" class="form-control" required>
    <option value="05" selected>Cédula</option>
    <option value="04">RUC</option>
    <option value="06">Pasaporte</option>
  </select>
</div>
```

### **Archivo 4: `views_nuevas.py`**
```python
# AGREGAR en creación de GuiaRemision:
tipo_identificacion_transportista=request.POST.get('tipo_identificacion_transportista', '05'),
dir_establecimiento=empresa.direccion or 'N/A',
rise=request.POST.get('rise', ''),
obligado_contabilidad=request.POST.get('obligado_contabilidad', ''),
contribuyente_especial=request.POST.get('contribuyente_especial', ''),
```

### **Archivo 5: `xml_generator_guia.py`**
```python
# ACTUALIZAR _generar_info_guia_remision() para incluir:
- tipoIdentificacionTransportista (NUEVO)
- dirEstablecimiento (NUEVO)
- rise (si existe)
- obligadoContabilidad (si existe)
- contribuyenteEspecial (si existe)
```

---

## ✅ VALIDACIÓN FINAL

Para que el XML sea 100% válido contra el XSD del SRI, necesitas:

1. **Migración de base de datos** con los 5 campos nuevos
2. **Actualizar formulario HTML** con tipo_identificacion_transportista
3. **Actualizar views_nuevas.py** para capturar nuevos campos
4. **Actualizar xml_generator_guia.py** para incluir campos en XML
5. **Validar XML contra XSD** usando lxml

### Comando de validación:
```python
from lxml import etree

xsd_doc = etree.parse('inventario/guia_remision/GuiaRemision_V1.1.0.xsd')
xsd = etree.XMLSchema(xsd_doc)

xml_doc = etree.parse('ruta/al/xml/generado.xml')
is_valid = xsd.validate(xml_doc)

if not is_valid:
    print(xsd.error_log)
```

---

## 🎯 PLAN DE ACCIÓN INMEDIATO

### Paso 1: Migración (5 minutos)
```bash
python manage.py makemigrations inventario
python manage.py migrate inventario
```

### Paso 2: Actualizar Form HTML (10 minutos)
- Agregar campo `tipo_identificacion_transportista`
- Agregar campos opcionales (rise, obligado_contabilidad, contribuyente_especial)

### Paso 3: Actualizar Views (5 minutos)
- Capturar nuevos campos en POST

### Paso 4: Actualizar XML Generator (15 minutos)
- Incluir todos los campos en `_generar_info_guia_remision()`
- Validar estructura contra XSD

### Paso 5: Probar (30 minutos)
- Llenar formulario completo
- Generar XML
- Validar contra XSD
- Enviar a SRI ambiente de pruebas

---

## 📊 ESTADÍSTICAS

**Campos Totales Requeridos por SRI:** ~35 campos  
**Campos Implementados:** ~28 campos (80%)  
**Campos Faltantes Críticos:** 1 (tipo_identificacion_transportista)  
**Campos Faltantes Opcionales:** 6  

**Tiempo Estimado para Completar al 100%:** 45 minutos  
**Prioridad:** 🔴 ALTA (El campo crítico bloquea la autorización del SRI)
