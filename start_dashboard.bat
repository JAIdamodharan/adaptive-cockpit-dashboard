@echo off
REM AI-Powered Adaptive Vehicle Dashboard - Windows Startup Script

echo ========================================
echo   Adaptive Vehicle Dashboard System
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Virtual environment not found!
    echo Please run: python -m venv venv
    echo Then run: venv\Scripts\activate
    echo Then run: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found! Please install Python 3.8+
    pause
    exit /b 1
)

REM Check if dependencies are installed
echo Checking dependencies...
python -c "import PyQt5" >nul 2>&1
if errorlevel 1 (
    echo Dependencies not installed!
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Check if models directory exists
if not exist "models\shape_predictor_68_face_landmarks.dat" (
    echo.
    echo WARNING: Facial landmark model not found!
    echo Please download from: http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
    echo Extract to: models\shape_predictor_68_face_landmarks.dat
    echo.
    echo Press any key to continue anyway (will use fallback mode)...
    pause
)

REM Start the application
echo.
echo Starting Adaptive Dashboard System...
echo.
cd src
python main.py

REM Deactivate virtual environment
deactivate

echo.
echo Dashboard system has been closed.
pause
