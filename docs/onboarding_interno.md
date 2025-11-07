# Onboarding interno

Este documento resume los pasos mínimos para incorporar a nuevas personas del equipo técnico
al ecosistema de Catalina Facturador.

## Cuentas administrativas

* Solicita al equipo de infraestructura la creación de un usuario superadministrador en el
  panel principal (`ROOT_ADMIN_URL`).
* Configura el acceso a través de la VPN corporativa y verifica que la IP esté incluida en la
  allowlist definida mediante `ADMIN_IP_ALLOWLIST`.
* **Activa MFA/OTP obligatorio**: todos los superadministradores deben registrar un segundo
  factor basado en OTP (Google Authenticator, 1Password, etc.) antes de recibir credenciales
  de producción. El alta queda documentada en el gestor de accesos interno.
* Realiza una prueba de inicio de sesión con MFA habilitado y registra la evidencia (captura o
  video corto) en la carpeta compartida de seguridad.

## Accesos a servicios auxiliares

* Solicita acceso de solo lectura al bucket S3 que almacena las firmas electrónicas.
* Habilita permisos en los tableros de monitoreo (Sentry y logs de Redis) para el nuevo
  integrante.
* Asegúrate de que la persona conozca el procedimiento de rotación de credenciales y las
  políticas de respuesta a incidentes vigentes.
