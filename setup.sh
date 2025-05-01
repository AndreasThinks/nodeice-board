#!/bin/bash

# Nodeice Board Setup Script
# This script helps set up the Nodeice Board application on your system.

set -e  # Exit on error

echo "===== Nodeice Board Setup ====="

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
python_major=$(echo $python_version | cut -d. -f1)
python_minor=$(echo $python_version | cut -d. -f2)

if [ "$python_major" -lt 3 ] || [ "$python_major" -eq 3 -a "$python_minor" -lt 9 ]; then
    echo "Error: Nodeice Board requires Python 3.9 or higher."
    echo "Current Python version: $python_version"
    exit 1
fi

echo "Python version $python_version - OK"

# Check if virtualenv exists and create if not
if ! command -v virtualenv >/dev/null 2>&1; then
    echo "Installing virtualenv..."
    pip3 install virtualenv
fi

# Create a virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    virtualenv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install the package in development mode
echo "Installing Nodeice Board and dependencies..."
pip install -e .

echo ""
echo "===== Setup Complete! ====="
echo ""
echo "To run Nodeice Board:"
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Make sure your Meshtastic device is connected to your computer"
echo ""
echo "3. Run the application:"
echo "   python main.py"
echo ""
echo "For more options, run:"
echo "   python main.py --help"
echo ""
echo "To set up as a service on Raspberry Pi, see the instructions in README.md"
echo ""
