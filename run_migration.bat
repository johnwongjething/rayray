@echo off
echo ========================================
echo Railway Database Migration Tool
echo ========================================
echo.

echo This script will migrate your Railway database to use timezone-aware timestamps.
echo.

REM Check if PowerShell is available
powershell -Command "Write-Host 'PowerShell is available'" >nul 2>&1
if errorlevel 1 (
    echo ERROR: PowerShell is not available on this system.
    echo Please install PowerShell and try again.
    pause
    exit /b 1
)

REM Get database URL from user
set /p DATABASE_URL="Enter your Railway database URL (postgresql://...): "

if "%DATABASE_URL%"=="" (
    echo ERROR: Database URL is required.
    pause
    exit /b 1
)

echo.
echo Starting migration...
echo.

REM Run the PowerShell script
powershell -ExecutionPolicy Bypass -File "migrate_railway_db.ps1" -DatabaseUrl "%DATABASE_URL%"

echo.
echo Migration completed. Press any key to exit.
pause 