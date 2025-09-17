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
