@echo off
title FaceIQ - Face Expression Detection System
color 0A

echo =====================================================
echo    FaceIQ - Real-World Face Expression Detection
echo =====================================================
echo.

:: Check Python
python --version 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+ from python.org
    pause
    exit /b 1
)

:: Install dependencies if not done
echo [1/2] Installing/verifying dependencies...
python -m pip install flask flask-socketio flask-cors opencv-python deepface tf-keras numpy pillow fpdf2 eventlet --quiet

echo [2/2] Starting FaceIQ server...
echo.
echo Open your browser at: http://localhost:5000
echo Press Ctrl+C to stop.
echo.

python app.py

pause
