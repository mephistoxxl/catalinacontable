# MIGRACIÓN SQLITE → POSTGRESQL - PROYECTO SISFACT

## ✅ Estado Actual: PREPARADO PARA MIGRACIÓN

### 🔧 **Cambios Realizados:**

1. **✅ Backup de datos SQLite completado**
   - Archivo: `backup_sqlite_data.json`
   - 43 registros exportados correctamente

2. **✅ Configuración dual SQLite/PostgreSQL implementada**
   - `settings.py` actualizado con configuración flexible
   - Variable `USE_POSTGRESQL` en `.env` para controlar la base de datos

3. **✅ Dependencias instaladas**
   - `psycopg2-binary` (driver PostgreSQL)
   - `cryptography` (requerido por el proyecto)

4. **✅ Scripts de migración creados**
   - `backup_sqlite.py` - Backup de datos
   - `migrate_to_postgresql.py` - Migración automática

### 🎯 **Para completar la migración necesitas:**

#### OPCIÓN A: PostgreSQL Local (Recomendado)
```bash
# 1. Descargar e instalar PostgreSQL
# https://www.postgresql.org/download/windows/
# Usuario: postgres, Contraseña: postgres, Puerto: 5432

# 2. Crear base de datos
createdb -U postgres sisfact_db

# 3. Migrar
python migrate_to_postgresql.py

# 4. Hacer permanente el cambio
# Editar .env: USE_POSTGRESQL=true
```

#### OPCIÓN B: PostgreSQL con Docker
```bash
# 1. Iniciar Docker Desktop

# 2. Ejecutar PostgreSQL en contenedor
docker run --name sisfact-postgres -e POSTGRES_DB=sisfact_db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:15

# 3. Migrar
python migrate_to_postgresql.py
```

#### OPCIÓN C: PostgreSQL en la nube (Gratis)
```bash
# 1. Crear cuenta en https://www.elephantsql.com/
# 2. Crear instancia gratuita
# 3. Actualizar .env con los datos de conexión
# 4. python migrate_to_postgresql.py
```

### 🔄 **Alternar entre bases de datos:**

```bash
# Usar SQLite
# En .env: USE_POSTGRESQL=false
python manage.py runserver

# Usar PostgreSQL
# En .env: USE_POSTGRESQL=true
python manage.py runserver
```

### 📁 **Archivos modificados:**
- ✅ `sistema/settings.py` - Configuración dual
- ✅ `.env` - Variables de entorno
- ✅ `requirements.txt` - Ya incluye psycopg2-binary
- ✅ `backup_sqlite_data.json` - Backup completo
- ✅ Scripts de migración creados

### 🚀 **Ventajas de PostgreSQL:**
- ✅ Mejor rendimiento con múltiples usuarios
- ✅ Transacciones ACID completas
- ✅ Tipos de datos avanzados
- ✅ Mejor para producción
- ✅ Escalabilidad

El proyecto está **100% preparado** para la migración. Solo necesitas tener PostgreSQL ejecutándose y ejecutar el script de migración.
