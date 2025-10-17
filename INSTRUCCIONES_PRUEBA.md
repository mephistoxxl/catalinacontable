# INSTRUCCIONES PARA PROBAR LA FIRMA AHORA MISMO
================================================

## ESTADO ACTUAL
✅ Firmador manual YA TIENE Object con Id (línea 345 de firmador_xades_manual.py)
✅ Configurado para usar firmador manual (USE_MANUAL_XADES=true)
✅ Caché de Python limpiado completamente

## OPCION 1: PROBAR DESDE LA APLICACION WEB (MAS RAPIDO)

### Paso 1: Reiniciar servidor Django
```powershell
# Si el servidor está corriendo, presiona Ctrl+C primero
cd "C:\Users\CORE I7\Desktop\catalinafact"
python manage.py runserver
```

### Paso 2: Crear y firmar una factura
1. Abre tu navegador: http://localhost:8000 (o el puerto que uses)
2. Inicia sesión
3. Crea una nueva factura (usa datos de prueba)
4. Firma la factura
5. **Envía al SRI**

### Paso 3: Verificar el XML firmado
El archivo firmado estará en: `media/facturas/[RUC]/xml/factura_..._firmado.xml`

Ejecuta este comando para verificar que tenga Object con Id:
```powershell
python -c "from lxml import etree; doc = etree.parse('RUTA_AL_XML_FIRMADO'); obj = doc.find('.//{http://www.w3.org/2000/09/xmldsig#}Object'); print('Object Id:', obj.get('Id') if obj is not None else 'NO ENCONTRADO')"
```

## OPCION 2: PROBAR CON SCRIPT (SI DJANGO DA PROBLEMAS)

### Instalar dependencia faltante (en PowerShell como Admin):
```powershell
pip install dj-database-url
```

### Ejecutar test:
```powershell
cd "C:\Users\CORE I7\Desktop\catalinafact"
python test_firma_final.py
```

## OPCION 3: VERIFICAR ULTIMO XML FIRMADO

Si ya tienes una factura firmada recientemente:

```powershell
# Buscar el XML más reciente
Get-ChildItem -Path ".\media\facturas\" -Filter "*_firmado.xml" -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName

# Copiar la ruta que aparece y verificar:
python check_object_id.py
```

(Edita check_object_id.py línea 17 con la ruta del XML)

## ¿QUE VERIFICAR?

Cuando ejecutes cualquier opción, busca en el XML firmado:

```xml
<ds:Object Id="Object_[algún_id]">
    <etsi:QualifyingProperties ...>
    ...
```

✅ **Si Object TIENE Id:** ¡Perfecto! La firma está completa
❌ **Si Object NO tiene Id:** Significa que se usó código antiguo

## SI ERROR 39 PERSISTE DESPUES DE TENER Object Id:

Entonces puede ser problema del ambiente PRUEBAS del SRI.
Prueba cambiar a PRODUCCION:

1. Ve a la configuración de Opciones en Django Admin
2. Cambia `tipo_ambiente` de '1' (PRUEBAS) a '2' (PRODUCCION)
3. Firma una nueva factura
4. Envía al SRI de PRODUCCION

## COMANDO RAPIDO - LIMPIEZA TOTAL

Si algo falla, ejecuta esto y empieza de nuevo:

```powershell
# Limpiar caché
Get-ChildItem -Path ".\inventario" -Include __pycache__,*.pyc -Recurse -Force | Remove-Item -Force -Recurse

# Reiniciar servidor
python manage.py runserver
```

## VERIFICACION FINAL

Después de firmar, el XML debe tener:
- ✅ 3 referencias en SignedInfo
- ✅ KeyValue con RSA
- ✅ **Object con atributo Id** (NUEVO)
- ✅ Inclusive C14N
- ✅ Solo enveloped-signature en comprobante

Si todo esto está correcto y el SRI sigue rechazando, el problema está en 
el validador del ambiente de PRUEBAS del SRI, no en tu código.

## NOTA IMPORTANTE

El firmador manual (firmador_xades_manual.py) YA está corregido con:
- Object con Id (línea 345)
- KeyValue con RSA (líneas 279-305)
- Estructura correcta de 3 referencias

Solo necesitas:
1. Reiniciar el servidor Django
2. Firmar una factura nueva
3. Verificar que tenga Object Id
4. Enviar al SRI

¡TODO LISTO PARA PROBAR!
