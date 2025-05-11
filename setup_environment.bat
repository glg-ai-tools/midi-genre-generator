@echo off
echo Setting up Python virtual environment...

set VENV_DIR=.venv
set PYTHON_EXE=python

REM Check if Python is available
%PYTHON_EXE% --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not found in your PATH. Please install Python and add it to your PATH.
    goto :eof
)

REM Remove existing virtual environment for a clean setup (optional)
if exist "%VENV_DIR%\" (
    echo Removing existing virtual environment: %VENV_DIR%
    rmdir /s /q "%VENV_DIR%"
    if errorlevel 1 (
        echo Warning: Could not remove existing virtual environment. It might be in use.
    )
)

echo Creating virtual environment: %VENV_DIR%
%PYTHON_EXE% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo Error: Failed to create virtual environment.
    goto :eof
)

echo Activating virtual environment and installing requirements...

REM Install requirements using pip from the virtual environment
call "%VENV_DIR%\Scripts\activate.bat" && (
    echo Upgrading pip...
    python -m pip install --upgrade pip
    echo Installing packages from requirements.txt...
    python -m pip install -r requirements.txt
)

if errorlevel 1 (
    echo Error: Failed to install requirements.
    echo Please check your internet connection and requirements.txt file.
) else (
    echo Environment setup complete!
    echo To activate the environment in a new terminal, run: %VENV_DIR%\Scripts\activate.bat
)

:eof
pause