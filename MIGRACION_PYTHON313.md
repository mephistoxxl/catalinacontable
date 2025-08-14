# Migración a Python 3.13+ - Sistema de Facturación Electrónica

## 📋 Resumen
Este documento describe los pasos necesarios para migrar el sistema de facturación electrónica a Python 3.13+ sin problemas de compatibilidad con el módulo `cgi`.

## ⚠️ Problema
Python 3.13+ ha eliminado el módulo `cgi`, lo que puede causar errores en:
- Django (multipart parser)
- Scripts de verificación de firma
- Otras dependencias que usen `cgi`

## ✅ Solución Implementada

### 1. Paquete legacy-cgi
Se utiliza el paquete `legacy-cgi` como reemplazo directo del módulo `cgi` eliminado.

### 2. Archivos Actualizados
- `manage.py`: Añadida compatibilidad con legacy-cgi
- `sistema/wsgi.py`: Añadida compatibilidad con legacy-cgi
- `requirements_python313_final.txt`: Nuevas dependencias compatibles
- `instalar_python313.py`: Script de instalación automatizada

### 3. Dependencias Actualizadas
```
django>=5.0,<6.0
cryptography>=41.0.0
reportlab>=4.0.0
pyhanko>=0.20.0
legacy-cgi>=2.0.0
pyhanko-certvalidator>=0.20.0
Pillow>=10.0.0
lxml>=4.9.0
zeep>=4.2.0
qrcode>=7.4.0
python-barcode>=0.15.0
```

## 🚀 Pasos de Migración

### Paso 1: Verificar Python
```bash
python --version
# Debe mostrar Python 3.13.x
```

### Paso 2: Instalar Dependencias
```bash
# Opción 1: Usar el script automatizado
python instalar_python313.py

# Opción 2: Instalar manualmente
python -m pip install -r requirements_python313_final.txt
```

### Paso 3: Verificar Instalación
```bash
# Verificar que legacy-cgi esté instalado
python -c "import legacy_cgi; print('legacy-cgi disponible')"

# Verificar Django
python manage.py check
```

### Paso 4: Actualizar Base de Datos
```bash
python manage.py makemigrations
python manage.py migrate
```

### Paso 5: Probar PDF Signing
```bash
# Iniciar servidor
python manage.py runserver

# Generar una factura y descargar el RIDE firmado
```

## 🔧 Solución de Problemas

### Error: "cannot import name 'cgi'"
**Causa**: legacy-cgi no está instalado
**Solución**:
```bash
python -m pip install legacy-cgi
```

### Error: "No module named 'cgi'"
**Causa**: Compatibilidad no aplicada
**Solución**: Asegúrate de que los archivos `manage.py` y `wsgi.py` tengan la compatibilidad con legacy-cgi.

### Error: "Django version incompatible"
**Causa**: Django versión antigua
**Solución**:
```bash
python -m pip install django>=5.0
```

## 📊 Verificación

### Comandos de Prueba
```bash
# Verificar todas las dependencias
python -c "
import django
import cryptography
import reportlab
import pyhanko
import legacy_cgi
print('✅ Todas las dependencias están disponibles')
"

# Verificar PDF signing
python -c "
from inventario.sri.pdf_firmador import PDFFirmador
print('✅ PDF signing disponible')
"
```

### Prueba de RIDE Firmado
1. Crea una nueva factura en el sistema
2. Genera el RIDE PDF
3. Descarga el PDF firmado
4. Verifica que el PDF contenga la firma electrónica

## 📝 Notas Importantes

### Compatibilidad con SRI
- La firma electrónica sigue siendo válida para el SRI
- Los certificados .p12 continúan funcionando normalmente
- No hay cambios en el formato de los documentos electrónicos

### Entornos de Producción
- Asegúrate de actualizar `wsgi.py` en producción
- Verifica que el servidor WSGI (Apache, Nginx) use Python 3.13+
- Actualiza los entornos virtuales

### Entornos Virtuales
```bash
# Crear nuevo entorno virtual con Python 3.13
python3.13 -m venv venv313
source venv313/bin/activate  # Linux/Mac
venv313\Scripts\activate      # Windows

# Instalar dependencias
pip install -r requirements_python313_final.txt
```

## 🔄 Rollback
Si necesitas revertir a Python 3.11 o 3.12:

1. Desactiva el entorno virtual actual
2. Crea un nuevo entorno con Python 3.11/3.12
3. Instala las dependencias originales
4. Restaura los archivos originales de manage.py y wsgi.py

## 📞 Soporte
Si encuentras problemas durante la migración:
1. Verifica la versión de Python: `python --version`
2. Verifica las dependencias: `python -m pip list`
3. Ejecuta las pruebas de verificación anteriores
4. Revisa los logs de Django para errores específicos

## ✅ Checklist de Migración

- [ ] Python 3.13+ instalado
- [ ] legacy-cgi instalado
- [ ] Django 5.0+ instalado
- [ ] manage.py actualizado
- [ ] wsgi.py actualizado
- [ ] Base de datos migrada
- [ ] RIDE firmado generado exitosamente
- [ ] Pruebas de firma electrónica completadas