@echo off
cd /d %~dp0

echo.
echo ================================================================================
echo LIMPIEZA PROFUNDA Y REINICIO FORZADO
echo ================================================================================
echo.

echo [1/6] Matando TODOS los procesos Python...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul
timeout /t 3 /nobreak >nul
echo [OK] Procesos Python detenidos
echo.

echo [2/6] Eliminando cache Python recursivamente...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul
echo [OK] Cache Python eliminado
echo.

echo [3/6] Eliminando XMLs corruptos...
del /F /Q "media\facturas\2390054060001\xml\*.xml" 2>nul
del /F /Q "media\facturas\2390054060001\xml_firmado\*.xml" 2>nul
echo [OK] XMLs eliminados
echo.

echo [4/6] Eliminando PDFs...
del /F /Q "media\facturas\2390054060001\pdf\*.pdf" 2>nul
echo [OK] PDFs eliminados
echo.

echo [5/6] Verificando cambio a lxml...
findstr /C:"lxml" inventario\sri\xml_generator.py >nul
if %errorlevel% equ 0 (
    echo [OK] xml_generator.py usa lxml correctamente
) else (
    echo [ERROR] xml_generator.py NO tiene el cambio a lxml
    pause
    exit /b 1
)
echo.

echo [6/6] Iniciando servidor Django...
echo.
echo ================================================================================
echo SERVIDOR LIMPIO - REINICIO FORZADO
echo ================================================================================
echo.
echo TESTING:
echo 1. Abre http://localhost:8000
echo 2. Crea factura 73 (numero 25)
echo 3. ANTES de enviar, verifica el XML:
echo    - Abre: media\facturas\2390054060001\xml\factura_001_999_000000025.xml
echo    - Busca: "TELEFONO" o "DIRECCION"
echo    - Debe decir: TELÉFONO (con acento, sin garabatos)
echo 4. Si esta correcto, firma y envia
echo.
echo ================================================================================
echo.

python manage.py runserver
