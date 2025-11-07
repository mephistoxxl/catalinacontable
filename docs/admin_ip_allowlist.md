# Configuración de allowlist para el panel de administración

Para proteger los paneles de administración (`ROOT_ADMIN_URL` y rutas multi-tenant) se utiliza el
middleware `AdminIPAllowlistMiddleware`. La política de acceso se controla mediante variables de
entorno obligatorias en producción.

## Variables obligatorias

| Variable | Descripción |
| --- | --- |
| `ADMIN_IP_ALLOWLIST` | Lista separada por comas con IPs o redes CIDR autorizadas para ingresar al panel. Ejemplo: `203.0.113.10/32,198.51.100.0/24`. |
| `ROOT_ADMIN_URL` | Prefijo del panel de administración principal. Define la ruta `/<<ROOT_ADMIN_URL>>/`. |

Si se utiliza un proveedor que añade encabezados confiables (por ejemplo, una VPN corporativa o
Cloudflare), también se pueden definir las siguientes variables opcionales:

| Variable | Descripción |
| --- | --- |
| `ADMIN_TRUSTED_HEADER` | Nombre del encabezado HTTP que debe inspeccionar el middleware (por ejemplo, `HTTP_X_VPN_ID`). |
| `ADMIN_TRUSTED_HEADER_VALUES` | Lista separada por comas con los valores aceptados para el encabezado confiable. |

## Configuración en Heroku

Ejecuta los siguientes comandos para registrar las variables obligatorias en la aplicación de Heroku:

```bash
heroku config:set ADMIN_IP_ALLOWLIST="203.0.113.10/32,198.51.100.0/24" \
  ROOT_ADMIN_URL="super-admin" --app <tu-app-heroku>
```

En caso de emplear un encabezado confiable, añade también:

```bash
heroku config:set ADMIN_TRUSTED_HEADER="HTTP_X_VPN_ID" \
  ADMIN_TRUSTED_HEADER_VALUES="vpn-prod" --app <tu-app-heroku>
```

> Sustituye las IPs y valores de ejemplo por los de tu VPN o redes autorizadas.

Guarda la definición de las IPs autorizadas dentro del equipo de infraestructura y actualiza estos
valores cuando se modifique la lista de acceso.

