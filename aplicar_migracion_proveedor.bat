@echo off
echo ================================
echo  APLICANDO MIGRACIÓN PROVEEDOR
echo ================================

echo.
echo [1/2] Ejecutando migración...
python manage.py migrate inventario 0073 --verbosity=2

echo.
echo [2/2] Verificando estado de migraciones...
python manage.py showmigrations inventario

echo.
echo ================================
echo  MIGRACIÓN COMPLETADA
echo ================================
echo.
echo ✅ El modelo Proveedor ahora tiene los mismos campos que Cliente:
echo    - tipoIdentificacion
echo    - identificacion_proveedor (ampliado a 13 chars)
echo    - razon_social_proveedor (ampliado a 200 chars)
echo    - nombre_comercial_proveedor (ampliado y opcional)
echo    - observaciones
echo    - convencional
echo    - tipoVenta
echo    - tipoRegimen
echo    - tipoProveedor
echo.
echo 🚀 Ya puedes usar el formulario actualizado de proveedor!
echo.
pause
