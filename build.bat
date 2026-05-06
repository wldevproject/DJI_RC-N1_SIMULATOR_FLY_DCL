@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

echo Checking PyInstaller...
"%PYTHON%" -m pip show pyinstaller >nul 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing it now...
    "%PYTHON%" -m pip install pyinstaller
    if errorlevel 1 (
        echo Failed to install PyInstaller.
        exit /b 1
    )
)

echo Building main controller app...
"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --name "DJI-RC-N1-Simulator" "%ROOT%main.py"
if errorlevel 1 exit /b 1

echo Building Xbox controller tester...
"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --windowed --name "Xbox-Controller-Tester" "%ROOT%test_controller_gui.py"
if errorlevel 1 exit /b 1

echo.
echo Build complete.
echo Output files are in the dist folder:
echo   %ROOT%dist\DJI-RC-N1-Simulator.exe
echo   %ROOT%dist\Xbox-Controller-Tester.exe
echo.
if /I not "%~1"=="/nopause" pause
