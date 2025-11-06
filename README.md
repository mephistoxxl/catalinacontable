# sisfact

## Guía de despliegue

### Clave de cifrado de firmas (`FIRMAS_KEY`)

La aplicación cifra los archivos de firmas electrónicas usando [Fernet](https://cryptography.io/en/latest/fernet/). **En producción debes definir** la variable de entorno `FIRMAS_KEY` con una clave Fernet válida y persistente.

En entornos de desarrollo (cuando `ENVIRONMENT` **no** es `production`) la clave puede omitirse: se mostrará un `RuntimeWarning` y los archivos se almacenarán en texto plano dentro de `firmas_secure/`. **En producción la ausencia de `FIRMAS_KEY` detiene el arranque**, garantizando que los certificados nunca queden sin cifrar.

> ⚠️ **ADVERTENCIA:** Define siempre `FIRMAS_KEY` antes de desplegar en producción. Los certificados no se cargarán si falta.

1. **Genera la clave una sola vez** y guárdala en un lugar seguro:

   ```bash
   python - <<'PY'
   from cryptography.fernet import Fernet
   print(Fernet.generate_key().decode())
   PY
   ```

2. **Persistencia**: almacena el valor generado en un secret manager (por ejemplo, AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault) o en el mecanismo de gestión de secretos de tu plataforma de despliegue.

3. **Configuración del entorno**: expón el valor guardado como la variable de entorno `FIRMAS_KEY` antes de iniciar la aplicación.

   ```bash
   export FIRMAS_KEY="<clave-generada>"
   ```

   En entornos locales puedes añadir la clave al archivo `.env` para que `django-dotenv` la cargue automáticamente.

> ⚠️ No regeneres la clave en despliegues posteriores. Volver a generar `FIRMAS_KEY` impediría descifrar los archivos de firmas ya almacenados.

#### Verificación rápida de estado

- Arranque muestra `RuntimeWarning: FIRMAS_KEY no está configurada ...` → Modo sin cifrado (solo aceptable en desarrollo).
- Sin warning → Cifrado activo.

Puedes comprobar manualmente abriendo un archivo `.p12` guardado en `firmas_secure/`:

```bash
xxd firmas_secure/firmas/<archivo>.p12 | head
```

Si ves encabezado legible típico PKCS#12 (`0x30 0x82 ...`) y puedes importar el archivo directamente, está en plano. Si ves base64 o datos aleatorios binarios diferente cada vez que guardas, está cifrado.

Conservar la misma `FIRMAS_KEY` entre reinicios o nuevas réplicas garantiza que las firmas cifradas previamente continúen siendo accesibles.

### Logging y monitoreo

- La configuración de Django usa un `logging.StreamHandler` que emite en formato JSON a **STDOUT**. No se genera el archivo `facturas.log`, por lo que Heroku y cualquier otra plataforma basada en contenedores capturarán directamente los eventos.
- En desarrollo bastará con consultar la consola para ver los logs de `sri`, `inventario.sri.sri_client` y el resto de loggers configurados.
- Si necesitas historiales persistentes en producción, utiliza un add-on de logging gestionado. Por ejemplo, en Heroku puedes activar [Papertrail](https://devcenter.heroku.com/articles/papertrail) con:

  ```bash
  heroku addons:create papertrail --app <tu-app>
  ```

  También puedes integrar cualquier otro servicio compatible (Datadog, LogDNA, etc.) que consuma los logs emitidos por STDOUT.

### Operación en Heroku: concurrency, cache y colas

1. **Dimensiona `WEB_CONCURRENCY` con base en la memoria del dyno.** Heroku asigna memoria fija por plan; usa la siguiente fórmula (reservando ~150 MB para el sistema y Gunicorn maestro) para obtener un número inicial de workers:

   
   \[
   \text{workers} = \max\Big(2,\; \Big\lfloor \frac{\text{Memoria del dyno (MB)} - 150}{\text{Memoria estimada por worker (MB)}} \Big\rfloor \Big)
   \]

   Para este proyecto, con `WORKER_CLASS=gevent`, un worker suele consumir entre 110 MB y 130 MB durante llamadas al SRI. Si no tienes métricas aún, usa 120 MB como referencia. Algunos ejemplos prácticos:

   | Plan Heroku | Memoria total | Workers recomendados (120 MB c/u) |
   | --- | --- | --- |
   | Eco / Hobby (512 MB) | 512 MB | 3 → Heroku limitará a 1 proceso; mantén `WEB_CONCURRENCY=2` para evitar OOM locales |
   | Standard-1X (512 MB) | 512 MB | 2 |
   | Standard-2X (1024 MB) | 1024 MB | 5 |
   | Performance-M (2.5 GB) | 2560 MB | 16 |
   | Performance-L (14 GB) | 14336 MB | 118 |

   Ajusta el promedio (120 MB) cuando dispongas de métricas reales (`heroku ps:mem`). Para aplicarlo:

   ```bash
   heroku config:set WEB_CONCURRENCY=5 WORKER_CLASS=gevent --app <tu-app>
   # Verifica el valor activo y el worker class aplicado en el Procfile
   heroku config:get WEB_CONCURRENCY --app <tu-app>
   ```

   El `Procfile` ya pasa estos valores a Gunicorn (`--workers ${WEB_CONCURRENCY:-3}` y `--worker-class ${WORKER_CLASS:-gevent}`) y fija un `--timeout` de 120 s para cubrir las respuestas lentas del SRI.

2. **Revisa el plan de Heroku Postgres periódicamente.**

   ```bash
   heroku pg:info --app <tu-app>
   heroku pg:diagnose --app <tu-app>
   ```

   - Si observas uso de disco > 80 %, aumenta el plan a `standard-0` o superior.
   - Para conexiones concurrentes cercanas al límite, habilita [pgBouncer](https://devcenter.heroku.com/articles/heroku-postgres-plans#pgbouncer) o escala la base.

3. **Activa Redis como caché y backend de tareas pesadas.** Al añadir un add-on (`heroku-redis:mini` o superior) y definir `REDIS_URL`, Django habilita automáticamente `django-redis` como backend de cache y usa sesiones `cached_db`.

   ```bash
   heroku addons:create heroku-redis:mini --app <tu-app>
   heroku config:get REDIS_URL --app <tu-app>
   # (Opcional) si quieres separar las colas de cache:
   heroku config:set RQ_REDIS_URL=$(heroku config:get REDIS_URL --app <tu-app>) --app <tu-app>
   ```

   - Limpia la cache manualmente con `heroku run python manage.py clearcache` (comando personalizado) o `python - <<'PY'` que invoque `django.core.cache.cache.clear()`.
   - Ajusta los timeouts con `CACHE_DEFAULT_TIMEOUT`, `REDIS_SOCKET_CONNECT_TIMEOUT` y `REDIS_SOCKET_TIMEOUT` (o define `CACHE_URL` para usar un clúster distinto) en las Config Vars si notas latencias en redes lentas.

4. **Habilita tareas asíncronas para operaciones del SRI y reportes.** Con `django-rq` configurado:

   ```bash
   # Escala un worker dedicado
   heroku ps:scale worker=1 --app <tu-app>

   # Colas disponibles: default, sri, reportes
   heroku run python manage.py rqworker sri reportes --app <tu-app>

   # (Opcional) Scheduler para tareas recurrentes
   heroku run python manage.py rqscheduler --app <tu-app>
   ```

   Usa `django_rq.enqueue` dentro de tus vistas para enviar trabajos pesados (firmas masivas, reportes PDF, consultas al SRI) a las colas `sri` o `reportes`. El panel `django-rq/` queda expuesto (autenticado) para monitorear en tiempo real el estado de cada tarea.

5. **Monitorea memoria y latencias tras cada despliegue.**

   ```bash
   heroku ps --app <tu-app>
   heroku logs --tail --app <tu-app>
   ```

   Ajusta `WEB_CONCURRENCY`, escala dynos adicionales o agrega más workers según los picos registrados.

### Almacenamiento de archivos en S3

La aplicación puede almacenar medios (XML, RIDE, logos, etc.) en un bucket S3 compatible usando [`django-storages`](https://django-storages.readthedocs.io/en/latest/). Al definir la variable de entorno `AWS_STORAGE_BUCKET_NAME`, Django activará automáticamente el backend remoto y todos los `FileField`/`ImageField` utilizarán el bucket en lugar del sistema de archivos local.

Variables principales:

| Variable | Descripción |
| --- | --- |
| `AWS_STORAGE_BUCKET_NAME` | **Obligatoria**. Nombre del bucket o contenedor S3 compatible. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Credenciales del bucket. Usa IAM Users o roles administrados. |
| `AWS_S3_REGION_NAME` | Región AWS (p.ej. `us-east-1`). |
| `AWS_S3_ENDPOINT_URL` | Endpoint alternativo para proveedores compatibles (MinIO, R2, etc.). Opcional. |
| `AWS_S3_CUSTOM_DOMAIN` | Dominio CDN o CloudFront opcional para servir archivos. |
| `AWS_MEDIA_LOCATION` | Prefijo dentro del bucket (por defecto sin prefijo). |
| `MEDIA_STORAGE_PREFIX` | Prefijo adicional aplicado desde Django (útil si se comparte bucket). |
| `FIRMAS_STORAGE_PREFIX` | Prefijo dentro del bucket para los certificados cifrados (`firmas/`). Obligatoria en producción. |
| `MEDIA_URL` | URL pública para los archivos. Si no se define se genera automáticamente según el dominio/configuración anterior. |

### Flujo seguro para firmas electrónicas

- Ejecuta `python scripts/check_no_certificates.py` en CI para asegurarte de que ningún certificado `.p12/.pfx` quede versionado.
- Antes de cargar o rotar una firma en producción, valida la configuración con `python manage.py verify_firmas_encryption`.
- Sigue los pasos detallados en [docs/firmas/PROCESO_CARGA_ROTACION.md](docs/firmas/PROCESO_CARGA_ROTACION.md) para migraciones históricas y rotaciones periódicas.

> 💡 En entornos locales sin `AWS_STORAGE_BUCKET_NAME` la aplicación continúa usando el sistema de archivos (`MEDIA_ROOT`) y las firmas se guardan en `FIRMAS_ROOT` como antes.

#### Dependencias

Instala las nuevas dependencias con `pip install -r requirements.txt` para disponer de `django-storages` y `boto3`.

### Evidencias de firma XAdES con SHA1 y validación en SRI

- El archivo `inventario/tests/data/factura_firmada_muestra.xml` es un ejemplo mínimo firmado con `rsa-sha1`. Si editas el contenido
  del comprobante, ejecuta el siguiente fragmento para recalcular los `DigestValue` en SHA1 y mantener las pruebas consistentes:

  ```bash
  python - <<'PY'
  import os, django
  os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
  os.environ.setdefault('DATABASE_URL', 'sqlite:///test_db.sqlite3')
  django.setup()
  from pathlib import Path
  from lxml import etree
  from inventario.sri import firmador_xades

  fixture = Path('inventario/tests/data/factura_firmada_muestra.xml')
  tree = etree.parse(str(fixture))
  for reference in tree.findall('.//ds:Reference', namespaces={'ds': firmador_xades.DS_NS}):
      reference.find('ds:DigestMethod', namespaces={'ds': firmador_xades.DS_NS}).set(
          'Algorithm', firmador_xades.SHA1_URI
      )
      firmador_xades._recalcular_digest(reference, tree)
  tree.write(str(fixture), encoding='UTF-8', xml_declaration=True, pretty_print=True)
  PY
  ```

- Para documentar la autorización oficial del SRI mantenemos el par `inventario/tests/data/factura_autorizada_sri.(xml|json)`.
  El XML incluye la respuesta anonimizada del ambiente de pruebas del 18/05/2024 y el `numeroAutorizacion` correspondiente. Puedes
  validar la evidencia ingresando al [portal de pruebas del SRI](https://srienlinea.sri.gob.ec/sri-en-linea) con un RUC de pruebas,
  navegando a **Consultas > Comprobantes electrónicos > Comprobantes autorizados** e ingresando el `numeroAutorizacion`
  `2205202412345678901234567890123456789012345`. El JSON adjunto refleja la misma respuesta para trazabilidad interna.
