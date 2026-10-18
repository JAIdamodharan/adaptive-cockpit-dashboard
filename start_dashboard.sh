#!/bin/bash
# AI-Powered Adaptive Vehicle Dashboard - Linux/Mac Startup Script

echo "========================================"
echo "  Adaptive Vehicle Dashboard System"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found!"
    echo "Please run: python -m venv venv"
    echo "Then run: source venv/bin/activate"
    echo "Then run: pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check Python installation
if ! command -v python &> /dev/null; then
    echo "Python not found! Please install Python 3.8+"
    exit 1
fi

echo "Python version:"
python --version

# Check if dependencies are installed
echo "Checking dependencies..."
if ! python -c "import PyQt5" &> /dev/null; then
    echo "Dependencies not installed!"
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if models directory exists
if [ ! -f "models/shape_predictor_68_face_landmarks.dat" ]; then
    echo ""
    echo "WARNING: Facial landmark model not found!"
    echo "Please download from: http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
    echo "Extract to: models/shape_predictor_68_face_landmarks.dat"
    echo ""
    echo "Press Enter to continue anyway (will use fallback mode)..."
    read
fi

# Start the application
echo ""
echo "Starting Adaptive Dashboard System..."
echo ""
cd src
python main.py

# Deactivate virtual environment
deactivate

echo ""
echo "Dashboard system has been closed."
