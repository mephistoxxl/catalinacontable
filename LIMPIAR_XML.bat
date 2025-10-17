@echo off
cd /d %~dp0
del /F /Q "media\facturas\2390054060001\xml\factura_001*000000023*.xml" 2>nul
echo.
echo ================================================================================
echo XMLs CORRUPTOS ELIMINADOS
echo ================================================================================
echo.
echo SIGUIENTE PASO:
echo 1. Inicia el servidor: python manage.py runserver
echo 2. Abre http://localhost:8000
echo 3. Crea una NUEVA factura (numero 24)
echo 4. Firma y envia al SRI
echo.
echo El XML ahora se generara con lxml (UTF-8 correcto)
echo Los acentos apareceran como TELEFONO y DIRECCION (sin garabatos)
echo.
pause
