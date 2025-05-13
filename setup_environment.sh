#!/bin/bash

# Setting up Python virtual environment
VENV_DIR=".venv"
PYTHON_EXE="python3"

# Check if Python is available
if ! command -v $PYTHON_EXE &> /dev/null
then
    echo "Error: Python is not found in your PATH. Please install Python and add it to your PATH."
    exit 1
fi

# Remove existing virtual environment for a clean setup (optional)
if [ -d "$VENV_DIR" ]; then
    echo "Removing existing virtual environment: $VENV_DIR"
    rm -rf "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "Warning: Could not remove existing virtual environment. It might be in use."
    fi
fi

# Create virtual environment
echo "Creating virtual environment: $VENV_DIR"
$PYTHON_EXE -m venv "$VENV_DIR"
if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment."
    exit 1
fi

# Activate virtual environment and install requirements
echo "Activating virtual environment and installing requirements..."
source "$VENV_DIR/bin/activate"
if [ $? -ne 0 ]; then
    echo "Error: Failed to activate virtual environment."
    exit 1
fi

echo "Upgrading pip..."
pip install --upgrade pip
if [ $? -ne 0 ]; then
    echo "Error: Failed to upgrade pip."
    exit 1
fi

echo "Installing packages from requirements.txt..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install requirements. Please check your internet connection and requirements.txt file."
    exit 1
fi

echo "Environment setup complete!"
echo "To activate the environment in a new terminal, run: source $VENV_DIR/bin/activate"
