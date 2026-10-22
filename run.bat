@echo off
REM Unbanded Patcher GUI launcher (Windows)
where python >nul 2>&1 || (echo Python not found on PATH & exit /b 1)
cd /d "%~dp0"
pythonw main.py
