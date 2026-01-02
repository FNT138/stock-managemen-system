@echo off
title Stock Management System
echo ========================================
echo   Stock Management System - Bicicleteria
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".stock\Scripts\activate.bat" (
    echo [!] Virtual environment not found. Creating...
    python -m venv .stock
    call .stock\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .stock\Scripts\activate.bat
)

echo.
echo [*] Starting application...
echo [*] Opening browser at http://localhost:8501
echo.
echo Press Ctrl+C to stop the server
echo.

REM Open browser after 3 seconds
start "" timeout /t 3 /nobreak >nul && start http://localhost:8501

REM Run Streamlit
streamlit run app.py --server.headless true

pause
