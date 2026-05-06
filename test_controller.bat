@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"
echo Starting Xbox Controller Tester GUI...
if exist "%PYTHON%" (
    "%PYTHON%" "%ROOT%test_controller_gui.py"
) else (
    echo Warning: .venv not found, using system Python.
    python "%ROOT%test_controller_gui.py"
)
pause
