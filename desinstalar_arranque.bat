@echo off
setlocal

set TASK_NAME=VulcamoiaWatcher

echo.
echo  Eliminando tarea "%TASK_NAME%"...
echo.

schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

if %errorlevel% == 0 (
    echo [OK] Tarea eliminada. El watcher ya no arrancara automaticamente.
) else (
    echo [INFO] La tarea no existia o ya fue eliminada.
)

:: Tambien matar procesos pythonw que puedan estar corriendo watcher.py
taskkill /f /im pythonw.exe >nul 2>&1
echo [OK] Proceso pythonw detenido (si estaba corriendo).

echo.
pause
endlocal
