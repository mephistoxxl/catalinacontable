# sisfact

## Guía de despliegue

### Clave de cifrado de firmas (`FIRMAS_KEY`)

La aplicación cifra los archivos de firmas electrónicas usando [Fernet](https://cryptography.io/en/latest/fernet/). **En producción debes definir** la variable de entorno `FIRMAS_KEY` con una clave Fernet válida y persistente. 

Desde la actualización reciente, si `FIRMAS_KEY` no está presente el sistema **ya no se detiene**: los archivos de firma se almacenarán en texto plano dentro del directorio `firmas_secure/`. Esto facilita el desarrollo y pruebas iniciales, pero:

> ⚠️ **ADVERTENCIA:** No ejecutes un entorno productivo sin `FIRMAS_KEY`. Los certificados quedarían sin cifrar en disco.

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
| `FIRMAS_STORAGE_PREFIX` | Prefijo dentro del bucket para los certificados cifrados (`firmas/`). Por defecto `firmas_secure`. |
| `MEDIA_URL` | URL pública para los archivos. Si no se define se genera automáticamente según el dominio/configuración anterior. |

> 💡 En entornos locales sin `AWS_STORAGE_BUCKET_NAME` la aplicación continúa usando el sistema de archivos (`MEDIA_ROOT`) y las firmas se guardan en `FIRMAS_ROOT` como antes.

#### Dependencias

Instala las nuevas dependencias con `pip install -r requirements.txt` para disponer de `django-storages` y `boto3`.
