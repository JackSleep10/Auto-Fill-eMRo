@echo off
chcp 65001 >nul
title Thai Lion Air - GSE Work Order Creator
cd /d "%~dp0"

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "C:\Users\acklo\.local\bin\python3.11.exe" (
    set "PYTHON_EXE=C:\Users\acklo\.local\bin\python3.11.exe"
) else if exist "%USERPROFILE%\.local\bin\python3.11.exe" (
    set "PYTHON_EXE=%USERPROFILE%\.local\bin\python3.11.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" run_system.py
pause
