@echo off
setlocal
cd /d C:\InstructionValidation

if not exist ".venv\Scripts\streamlit.exe" (
    echo ERROR: Local virtual environment or Streamlit launcher was not found.
    echo Expected: C:\InstructionValidation\.venv\Scripts\streamlit.exe
    pause
    exit /b 1
)

.venv\Scripts\streamlit.exe run app.py
if errorlevel 1 (
    echo.
    echo Streamlit exited with an error.
    pause
)
