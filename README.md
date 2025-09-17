# sisfact

## Guía de despliegue

### Clave de cifrado de firmas (`FIRMAS_KEY`)

La aplicación cifra los archivos de firmas electrónicas usando [Fernet](https://cryptography.io/en/latest/fernet/). Es obligatorio definir la variable de entorno `FIRMAS_KEY` con una clave Fernet válida y persistente antes de iniciar el servicio; de lo contrario, el arranque fallará.

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

Conservar la misma `FIRMAS_KEY` entre reinicios o nuevas réplicas garantiza que las firmas cifradas previamente continúen siendo accesibles.
