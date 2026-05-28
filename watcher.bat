@echo off
cd /d "%~dp0"
echo =============================================
echo  Vulcamoia - Watcher de Facturas
echo  Monitorea la carpeta y envía a la web
echo  Dejar esta ventana abierta mientras se reparte
echo =============================================
echo.
python watcher.py
pause
