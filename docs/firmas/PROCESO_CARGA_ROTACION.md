# Proceso seguro de carga y rotación de firmas electrónicas

Este documento define el flujo operativo para cargar nuevas firmas electrónicas o rotar certificados existentes sin exponer los archivos en el repositorio.

## 1. Requisitos previos de configuración

Antes de trabajar con firmas en el entorno de producción:

1. Define las variables de entorno obligatorias:
   - `ENVIRONMENT=production`.
   - `AWS_STORAGE_BUCKET_NAME` con el bucket S3 dedicado para archivos sensibles.
   - `FIRMAS_STORAGE_PREFIX` con el prefijo (carpeta) exclusivo para firmas dentro del bucket.
   - `FIRMAS_KEY` con la clave Fernet urlsafe-base64 que se usará para cifrar los archivos.
2. Despliega la aplicación y ejecuta:

   ```bash
   python manage.py verify_firmas_encryption
   ```

   El comando falla si falta el cifrado, si no se está utilizando S3 o si el prefijo seguro no está definido. No cargues certificados hasta que el resultado sea **“EncryptedFirmaStorage está listo”**.

3. Añade el chequeo de CI `scripts/check_no_certificates.py` a tu pipeline (por ejemplo, GitHub Actions) para impedir que algún `.p12/.pfx` quede versionado:

   ```bash
   python scripts/check_no_certificates.py
   ```

   El comando devuelve un error si detecta certificados o claves privadas dentro del repositorio.

## 2. Migración inicial de firmas fuera de Git

1. Respaldar el directorio histórico `firmas_secure/firmas/` fuera del repositorio (por ejemplo, a un almacenamiento temporal cifrado).
2. Eliminar los archivos del repositorio y confirmar que `.gitignore` impide volver a añadirlos.
3. Con la aplicación desplegada y S3 listo, reimporta las firmas históricas ejecutando:

   ```bash
   python manage.py migrate_firmas_storage
   ```

   El comando realiza la validación de seguridad y sube cada certificado al backend configurado (S3), cifrándolo con `FIRMAS_KEY`. Opciones útiles:

   - `--dry-run`: muestra qué archivos se migrarían sin subirlos.
   - `--delete-source`: elimina el archivo local al terminar (úsalo solo cuando confirmes que el archivo ya está en S3).
   - `--limit <n>`: migra en lotes pequeños.

4. Tras la migración, verifica que no quedan archivos locales sensibles y elimina los respaldos temporales.

## 3. Carga de nuevas firmas

1. Antes de aceptar un nuevo certificado de un cliente, ejecuta nuevamente `python manage.py verify_firmas_encryption` para confirmar que la clave de cifrado y el backend remoto siguen activos.
2. Carga la firma mediante la interfaz de administración o el flujo previsto por la aplicación.
3. Confirma que el objeto se almacena cifrado en S3 (por ejemplo, descargando desde el bucket y verificando que el contenido sea binario cifrado).
4. Nunca conserves el `.p12/.pfx` en equipos compartidos; elimina cualquier copia local una vez completada la carga.

## 4. Rotación periódica de certificados

1. Solicita al cliente un nuevo certificado y respáldalo temporalmente en un medio seguro.
2. Ejecuta `python manage.py verify_firmas_encryption` para validar que el cifrado sigue habilitado.
3. Si cambiaste `FIRMAS_KEY`, vuelve a ejecutar `python manage.py migrate_firmas_storage --delete-source` para reescribir los certificados almacenados con la nueva clave.
4. Sube el nuevo archivo desde la aplicación. Al guardar, `EncryptedFirmaStorage` sobrescribe automáticamente la versión anterior en S3 manteniendo el historial fuera del repositorio.
5. Ejecuta `python scripts/check_no_certificates.py` en tu rama antes de abrir un PR, garantizando que ningún certificado quedó versionado.

Siguiendo este procedimiento se asegura que las firmas se almacenen exclusivamente en S3, cifradas y fuera del control de versiones.
