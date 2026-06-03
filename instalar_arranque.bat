@echo off
setlocal

:: ============================================================
::  Vulcamoia Watcher — Instalador de arranque automatico
::  Registra una Tarea Programada de Windows que corre
::  el watcher al iniciar sesion, sin ventana CMD.
::  REQUIERE ejecutar como Administrador.
:: ============================================================

set TASK_NAME=VulcamoiaWatcher
set VBS_PATH=%~dp0watcher_silencioso.vbs

echo.
echo  ============================================
echo   Vulcamoia Watcher - Instalador de arranque
echo  ============================================
echo.
echo  VBS : %VBS_PATH%
echo  Tarea: %TASK_NAME%
echo.

:: Verificar que el .vbs existe
if not exist "%VBS_PATH%" (
    echo [ERROR] No se encontro watcher_silencioso.vbs en %~dp0
    echo         Asegurate de ejecutar este .bat desde la carpeta del proyecto.
    pause
    exit /b 1
)

:: Crear tarea programada: al iniciar sesion, maxima prioridad, sin limite de tiempo
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "wscript.exe \"%VBS_PATH%\"" ^
    /sc onlogon ^
    /rl highest ^
    /f ^
    /delay 0001:00 ^
    >nul 2>&1

if %errorlevel% == 0 (
    echo [OK] Tarea "%TASK_NAME%" instalada correctamente.
    echo.
    echo      El watcher se iniciara automaticamente cada vez
    echo      que arranque Windows, sin abrir ninguna ventana.
    echo.
    echo      Para verificar: schtasks /query /tn "%TASK_NAME%"
    echo      Para desinstalar: ejecuta desinstalar_arranque.bat
) else (
    echo [ERROR] No se pudo instalar la tarea.
    echo         Proba ejecutar este archivo como Administrador:
    echo         Clic derecho ^> "Ejecutar como administrador"
)

echo.
pause
endlocal
