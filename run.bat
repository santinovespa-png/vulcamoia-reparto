@echo off
cd /d "%~dp0"

echo =============================================
echo  Vulcamoia - Reparto Buenos Aires
echo.
echo  Panel oficina:    http://localhost:8000
echo  Panel repartidor: http://localhost:8000
echo.
echo  Presiona Ctrl+C para detener.
echo =============================================
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
