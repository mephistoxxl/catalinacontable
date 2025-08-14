@echo off
echo 🔍 Verificando PDFs firmados en el sistema...
echo.
echo 📂 Buscando en: media\ride\
echo.

if exist "media\ride\*_firmado.pdf" (
    echo ✅ PDFs FIRMADOS ENCONTRADOS:
    echo.
    for %%f in ("media\ride\*_firmado.pdf") do (
        echo    📄 %%~nxf - %%~zf bytes
    )
    echo.
    echo 🎉 Tus RIDE PDFs están firmados electrónicamente!
) else (
    echo ❌ No se encontraron PDFs firmados.
    echo.
    echo 📋 Archivos PDF encontrados:
    if exist "media\ride\*.pdf" (
        for %%f in ("media\ride\*.pdf") do (
            echo    📄 %%~nxf - %%~zf bytes
        )
    ) else (
        echo    No hay archivos PDF en el directorio.
    )
)

echo.
echo 📍 Ubicación completa: %cd%\media\ride\
echo.
pause