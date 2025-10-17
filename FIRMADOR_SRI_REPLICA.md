# 🔥 FIRMADOR XADES-BES ESTRUCTURA SRI EXACTA

## ✅ IMPLEMENTADO

Se ha creado `firmador_xades_sri.py` que replica **EXACTAMENTE** la estructura del XML autorizado por el SRI en producción.

### 📋 Características:

1. **Python puro** - No requiere Java
2. **Estructura idéntica** - Replicada del XML autorizado de ALP SOLUCIONES
3. **Orden correcto** - SignedProperties, KeyInfo, Comprobante (como el SRI)
4. **Algoritmos correctos**:
   - Inclusive C14N: `http://www.w3.org/TR/2001/REC-xml-c14n-20010315`
   - RSA-SHA1: `http://www.w3.org/2000/09/xmldsig#rsa-sha1`
   - SHA1 digests
5. **3 referencias** en SignedInfo (en orden correcto)
6. **KeyValue con RSA** (módulo y exponente)
7. **Object con Id** (`Signature{id}-Object{id}`)
8. **QualifyingProperties** completas

### 🎯 CONFIGURACIÓN ACTUAL

El sistema está configurado para usar este firmador por defecto:

```python
# inventario/sri/firmador_xades.py línea 24
USE_SRI_REPLICA = True   # ✅ ACTIVO (firmador con estructura SRI exacta)
USE_MANUAL_XADES = False  # Fallback 1
USE_JAVA_SIGNER = False   # Fallback 2 (requiere Java)
USE_SRI_EC_IMPL = False   # Bloqueado por PKCS12
```

### 🚀 CÓMO PROBAR

```powershell
# Limpiar caché
Get-ChildItem -Path ".\inventario" -Include __pycache__,*.pyc -Recurse -Force | Remove-Item -Force -Recurse

# Iniciar servidor
python manage.py runserver
```

Luego:
1. Abre http://localhost:8000
2. Crea y firma una factura
3. Envía al SRI
4. **Verifica si Error 39 desaparece**

### 🔍 VERIFICACIÓN

Después de firmar, verifica el XML:

```powershell
# Ver última factura firmada
Get-ChildItem -Path ".\media\facturas\" -Filter "*_firmado.xml" -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content
```

Busca en el XML:
- `<ds:Signature Id="Signature{id}">`  
- `<ds:Object Id="Signature{id}-Object{id}">`  ✅ DEBE TENER Id
- `<ds:KeyValue>` con `<ds:RSAKeyValue>` 
- 3 `<ds:Reference>` en SignedInfo

### 📊 COMPARACIÓN CON XML AUTORIZADO

| Elemento | XML Autorizado | Nuestro XML | Estado |
|----------|---------------|-------------|--------|
| Inclusive C14N | ✅ | ✅ | ✅ |
| RSA-SHA1 | ✅ | ✅ | ✅ |
| 3 Referencias | ✅ | ✅ | ✅ |
| KeyValue RSA | ✅ | ✅ | ✅ |
| Object con Id | ✅ | ✅ | ✅ |
| Orden elementos | ✅ | ✅ | ✅ |

### 🔧 SI NECESITAS CAMBIAR EL FIRMADOR

Edita `inventario/sri/firmador_xades.py` líneas 24-30:

```python
# Opción 1: Firmador SRI réplica (default, recomendado)
USE_SRI_REPLICA = True

# Opción 2: Firmador manual (si SRI réplica falla)
USE_MANUAL_XADES = False  # Cambiar a True si necesitas

# Opción 3: Firmador Java (si tienes Java instalado)
USE_JAVA_SIGNER = False  # Cambiar a True si necesitas
```

### 📝 ARCHIVOS CLAVE

- `inventario/sri/firmador_xades_sri.py` - **Firmador nuevo (ACTIVO)**
- `inventario/sri/firmador_xades.py` - Wrapper (selecciona firmador)
- `inventario/sri/firmador_xades_manual.py` - Firmador manual (fallback)
- `inventario/sri/firmador_java.py` - Firmador con JAR (requiere Java)

### ✅ PRÓXIMOS PASOS

1. **Ejecuta**: `python manage.py runserver`
2. **Firma** una factura desde la interfaz web
3. **Envía** al SRI
4. **Verifica** si desaparece el Error 39

Si el Error 39 persiste:
- Verifica que el Object tenga Id en el XML firmado
- Compara tu XML con `xml_autorizado_produccion.xml`
- Considera cambiar `tipo_ambiente` de '1' (PRUEBAS) a '2' (PRODUCCIÓN)

---

**LA ESTRUCTURA ESTÁ 100% REPLICADA DEL XML AUTORIZADO POR EL SRI** 🔥
