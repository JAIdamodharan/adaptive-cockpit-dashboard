#!/usr/bin/env python3
"""
Install and verify all required packages for the adaptive dashboard system
"""

import subprocess
import sys

def install_package(package):
    """Install a package using pip"""
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def install_and_verify_packages():
    packages = [
        "PyQt5",
        "pyqtgraph",
        "numpy",
        "scipy",
        "pandas",
        "opencv-python",
        "mediapipe",
        "pytest",
        "pytest-qt",
        "pytest-cov"
    ]

    print("Installing required packages...\n")

    for package in packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✓ {package} already installed")
        except ImportError:
            print(f"Installing {package}...")
            try:
                install_package(package)
                print(f"✓ {package} installed successfully")
            except Exception as e:
                print(f"✗ Failed to install {package}: {e}")

    # Verify cv2 separately
    try:
        import cv2
        print(f"✓ OpenCV version: {cv2.__version__}")
    except ImportError:
        print("✗ OpenCV (cv2) not found")

    # Verify mediapipe
    try:
        import mediapipe as mp
        print(f"✓ MediaPipe version: {mp.__version__}")
    except ImportError:
        print("✗ MediaPipe not found")

    print("\n✅ Verification complete!")

if __name__ == "__main__":
    install_and_verify_packages()