@echo off
echo ========================================
echo REINICIAR SERVIDOR - CODIGO LXML ACTIVO
echo ========================================
echo.

echo [1] Matando procesos Python...
taskkill /F /IM python.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul
echo [OK] Procesos detenidos
echo.

echo [2] Limpiando cache de Python...
powershell -Command "Get-ChildItem -Path '.\inventario' -Include __pycache__,*.pyc -Recurse -Force | Remove-Item -Force -Recurse"
echo [OK] Cache limpiado
echo.

echo [3] Limpiando XMLs corruptos...
del /F /Q "media\facturas\2390054060001\xml\factura_*.xml" >nul 2>&1
del /F /Q "media\facturas\2390054060001\xml_firmado\factura_*.xml" >nul 2>&1
echo [OK] XMLs corruptos eliminados
echo.

echo [4] Iniciando servidor Django con LXML...
echo.
echo ========================================
echo IMPORTANTE - TESTING:
echo ========================================
echo 1. Abre http://localhost:8000
echo 2. Crea NUEVA factura (numero 25)
echo 3. Firma y envia al SRI
echo 4. Verifica XML: debe tener TELEFONO y DIRECCION (sin garabatos)
echo.
echo Presiona Ctrl+C para detener el servidor
echo ========================================
echo.

python manage.py runserver
