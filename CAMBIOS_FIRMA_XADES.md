# 🔒 Correcciones Aplicadas al Firmador XAdES-BES

## ✅ Cambios Realizados para Eliminar Error 39 (FIRMA INVALIDA)

### 1. **Limpieza de Atributo `id` (Líneas 37-72)**
**Problema**: Atributos `id` con namespace causaban rechazo del SRI
**Solución**: 
- Elimina TODOS los atributos `id` incluyendo los con namespace `{...}id`
- Establece solo `id="comprobante"` sin namespace
- Valida que no existan múltiples atributos `id`

```python
# ✅ Detecta: {http://example.com}id, Id, ID, id
# ✅ Elimina todos
# ✅ Establece solo: id="comprobante"
```

### 2. **Corrección de Base64 (Líneas 138-143)**
**Problema**: Espacios o encoding incorrecto en firmas Base64
**Solución**:
- Usa `decode('ascii')` explícitamente
- Elimina espacios con `.strip()`
- Líneas de exactamente 64 caracteres sin espacios finales

### 3. **Forzar SHA1 en Endesive (Líneas 291-337)**
**Problema**: Endesive usaba SHA256 por defecto
**Solución**:
- Monkey-patch al método `sha256` de endesive
- Fuerza SHA1 directamente en `signproc`
- Verifica y corrige si endesive ignora el parche

```python
# ✅ signproc siempre retorna: hashes.SHA1()
# ✅ Parche a endesive.xades.bes.BES.sha256
```

### 4. **Reconocimiento de Transform XPath (Línea 213)**
**Problema**: No reconocía el transform XPath usado por endesive
**Solución**:
- Detecta `rec-xpath-19991116` además de `enveloped-signature`
- Aplica la misma transformación (excluir firma del digest)

```python
if algo.endswith("#enveloped-signature") or "rec-xpath-19991116" in algo:
    # Excluir firma del cálculo del digest
```

### 5. **Corrección de CertDigest (Líneas 423-445)**
**Problema**: Digest del certificado usaba SHA256
**Solución**:
- Busca todos los `xades:CertDigest/ds:DigestMethod`
- Cambia algoritmo a SHA1
- Recalcula digest del certificado con SHA1

```python
# ✅ Extrae certificado X509 desde KeyInfo
# ✅ Calcula SHA1 del certificado DER
# ✅ Actualiza ds:DigestValue
```

### 6. **Logging Detallado y Diagnóstico (Múltiples líneas)**
**Problema**: Difícil diagnosticar qué causaba el error
**Solución**:
- Guarda XMLs intermedios en modo DEBUG:
  - `*_debug_post_endesive.xml` (después de endesive)
  - `*_debug_final.xml` (después de correcciones)
- Logging de cada cambio aplicado
- Validaciones finales que lanzan excepciones si algo falla

### 7. **Validaciones Estrictas Finales (Líneas 450-462)**
**Problema**: Firma se generaba pero con algoritmos incorrectos
**Solución**:
- Verifica que `SignatureMethod` sea RSA-SHA1
- Verifica que TODOS los `DigestMethod` sean SHA1
- Lanza excepción si detecta SHA256 residual

```python
# ✅ Si encuentra SHA256 → XAdESError
# ✅ No permite continuar con algoritmos incorrectos
```

## 📋 Checklist de Verificación

Antes de enviar al SRI, el código ahora verifica:

- [x] Atributo `id="comprobante"` sin namespace
- [x] SignatureMethod = `http://www.w3.org/2000/09/xmldsig#rsa-sha1`
- [x] Todos los DigestMethod = `http://www.w3.org/2000/09/xmldsig#sha1`
- [x] CertDigest usa SHA1
- [x] Transform XPath correctamente aplicado
- [x] Base64 sin espacios adicionales
- [x] SignatureValue generado con RSA-SHA1

## 🚀 Próximos Pasos

1. **Reiniciar el servidor Django**:
   ```powershell
   # Detener proceso actual
   # Reiniciar con: python manage.py runserver
   ```

2. **Activar logging DEBUG (opcional)**:
   ```python
   # En settings.py
   LOGGING = {
       'loggers': {
           'inventario.sri.firmador_xades': {
               'level': 'DEBUG',
           }
       }
   }
   ```

3. **Generar nueva factura de prueba**

4. **Revisar logs para confirmar**:
   - ✅ "Firma generada correctamente con RSA-SHA1"
   - ✅ "Todos los algoritmos validados correctamente"
   - ✅ "Todos los requisitos del SRI cumplidos"

5. **Enviar al SRI y verificar autorización**

## 🔍 Archivos de Debug

Si activas `logging.DEBUG`, encontrarás:
- `media/facturas/.../xml/*_debug_post_endesive.xml` - XML después de endesive
- `media/facturas/.../xml/*_debug_final.xml` - XML final con todas las correcciones

Estos archivos te permiten ver exactamente qué cambió en cada paso.

## ⚠️ Notas Importantes

1. **SHA1 está obsoleto** en seguridad moderna, pero el SRI aún lo requiere
2. Los cambios son **retrocompatibles** - código antiguo seguirá funcionando
3. Si el error persiste, revisa los archivos `*_debug_*.xml` para comparar
4. El código ahora **lanza excepciones** si detecta problemas en lugar de generar XMLs inválidos silenciosamente

---

**Fecha de aplicación**: 16 de Octubre, 2025
**Archivos modificados**: `inventario/sri/firmador_xades.py`
**Cachés limpiados**: `inventario/**/__pycache__/`
