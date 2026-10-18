#!/usr/bin/env python3

import subprocess
import sys
import importlib.util


def install_and_verify_packages():

    # Required packages
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
        "pytest-cov",
    ]

    print("Installing required packages...")

    for package in packages:
        try:
            # Try to import the package
            spec = importlib.util.find_spec(package.split(".")[0])
            if spec is not None:
                print(f"✓ {package} already available")
            else:
                print(f"Installing {package}...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"✓ {package} installed successfully")
        except Exception as e:
            print(f"✗ Failed to install/import {package}: {e}")

    # Special handling for opencv-python (cv2)
    try:
        import cv2
        print(f"✓ opencv-python (cv2) version: {cv2.__version__}")
    except ImportError:
        print("✗ Could not import cv2, trying to install opencv-python...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python"])

    # Special handling for mediapipe
    try:
        import mediapipe as mp
        print(f"✓ mediapipe version: {mp.__version__}")
    except ImportError:
        print("✗ Could not import mediapipe, trying to install...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "mediapipe"])

    print("\nVerification complete!")


if __name__ == "__main__":
    install_and_verify_packages()