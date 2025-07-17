@echo off
setlocal

REM Create virtual environment if it doesn't exist
if not exist "MantellaEnv" (
    echo Creating virtual environment...
    py -3.11 -m venv MantellaEnv
)

REM Activate the virtual environment
call MantellaEnv\Scripts\activate.bat

REM Run Mantella
python main.py

pause 