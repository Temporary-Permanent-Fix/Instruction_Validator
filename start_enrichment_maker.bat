@echo off
setlocal
cd /d "%~dp0"

echo Starting Packaging Instruction Enrichment & Decision Maker...
echo.

python --version
if errorlevel 1 (
    echo Python was not found on PATH.
    echo Install Python or use the company-approved runtime, then try again.
    pause
    exit /b 1
)

python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo Streamlit is missing or broken in this Python installation.
    echo.
    echo The app cannot start until Streamlit is available.
    echo Try reinstalling the project dependencies, or run it from a Python
    echo environment that has streamlit, pandas, and openpyxl installed.
    pause
    exit /b 1
)

python -m streamlit run app.py
if errorlevel 1 (
    echo.
    echo Streamlit exited with an error.
    pause
)
