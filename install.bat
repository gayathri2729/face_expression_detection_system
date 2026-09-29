@echo off
title FaceIQ - Installing Dependencies
color 0B

echo =====================================================
echo    FaceIQ - Installing Python Dependencies
echo =====================================================
echo.
echo Installing requirements...
echo.

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo =====================================================
echo    Installation complete!
echo    Run start.bat to launch FaceIQ.
echo =====================================================
pause
