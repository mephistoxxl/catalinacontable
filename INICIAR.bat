@echo off
echo ========================================
echo LIMPIAR CACHE Y REINICIAR SERVIDOR
echo ========================================
echo.

echo [1] Limpiando cache de Python...
powershell -Command "Get-ChildItem -Path '.\inventario' -Include __pycache__,*.pyc -Recurse -Force | Remove-Item -Force -Recurse"
echo [OK] Cache limpiado
echo.

echo [2] Iniciando servidor Django...
echo.
echo IMPORTANTE: Despues de que inicie el servidor:
echo 1. Abre http://localhost:8000
echo 2. Crea y firma una nueva factura
echo 3. Envia al SRI
echo.
echo Presiona Ctrl+C para detener el servidor
echo ========================================
echo.

python manage.py runserver
