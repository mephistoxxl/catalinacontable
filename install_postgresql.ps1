# Script para instalar PostgreSQL usando winget (Windows Package Manager)
Write-Host "=== INSTALANDO POSTGRESQL ===" -ForegroundColor Green

# Verificar si winget está disponible
if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "Instalando PostgreSQL usando winget..." -ForegroundColor Yellow
    winget install PostgreSQL.PostgreSQL
} else {
    Write-Host "winget no está disponible. Por favor instala PostgreSQL manualmente desde:" -ForegroundColor Red
    Write-Host "https://www.postgresql.org/download/windows/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Después de la instalación, configura:" -ForegroundColor Yellow
    Write-Host "- Usuario: postgres" -ForegroundColor White
    Write-Host "- Contraseña: postgres" -ForegroundColor White
    Write-Host "- Puerto: 5432" -ForegroundColor White
    exit 1
}

Write-Host "=== INSTALACIÓN COMPLETADA ===" -ForegroundColor Green
Write-Host "Por favor reinicia PowerShell y ejecuta el siguiente comando para crear la base de datos:" -ForegroundColor Yellow
Write-Host 'createdb -U postgres sisfact_db' -ForegroundColor Cyan
