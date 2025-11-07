# Evaluación de aislamiento multi-tenant

## Opción A: Row-Level Security en PostgreSQL

1. **Activar RLS** en las tablas multi-tenant críticas (`inventario_factura`, `inventario_producto`, `inventario_opciones`, `inventario_formapago`, etc.).
2. **Política por empresa**: crear una política que compare `empresa_id` contra una variable de sesión (`current_setting('app.empresa_id')`).
3. **Hook Django**: en el middleware que fija el tenant (por ejemplo `inventario.tenant.middleware.TenantMiddleware`), ejecutar `SET app.empresa_id = '<id>';` usando `connection.execute_wrapper` o `connection.cursor()`.

### Script SQL sugerido

```sql
-- Habilitar RLS
ALTER TABLE inventario_factura ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventario_producto ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventario_formapago ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventario_campoadicional ENABLE ROW LEVEL SECURITY;

-- Política genérica
CREATE POLICY factura_por_empresa ON inventario_factura
    USING (empresa_id = current_setting('app.empresa_id')::integer);

CREATE POLICY producto_por_empresa ON inventario_producto
    USING (empresa_id = current_setting('app.empresa_id')::integer);

CREATE POLICY formapago_por_empresa ON inventario_formapago
    USING (empresa_id = current_setting('app.empresa_id')::integer);

CREATE POLICY campoadicional_por_empresa ON inventario_campoadicional
    USING (empresa_id = current_setting('app.empresa_id')::integer);
```

> **Nota:** se recomienda envolver la creación de políticas con `CREATE POLICY ... IF NOT EXISTS` dentro de una migración específica para PostgreSQL.

## Opción B: Middleware de base de datos

Implementar un middleware (o `DatabaseWrapper.execute_wrapper`) que inserte `empresa_id` automáticamente en los `INSERT`/`UPDATE`. Esto reduce la exposición a errores humanos, pero no protege contra consultas directas vía consola o jobs externos. Requiere parsing del SQL o un ORM hook complejo.

## Recomendación

Priorizar Row-Level Security ya que aplica a cualquier cliente (ORM, consola, integraciones externas). Complementar con el middleware actual que fija el tenant para garantizar que `app.empresa_id` siempre esté presente antes de ejecutar consultas.
