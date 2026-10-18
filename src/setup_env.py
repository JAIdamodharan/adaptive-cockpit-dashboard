#!/usr/bin/env python3
"""
Setup script for AI-Powered Adaptive Dashboard System
Installs required dependencies and sets up the environment
"""

import subprocess
import sys
import os


def install_requirements():
    """Install required packages from requirements.txt"""
    print("Installing required packages...")

    try:
        # Install packages from requirements file
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Successfully installed required packages")
    except subprocess.CalledProcessError as e:
        print(f"✗ Error installing packages: {e}")
        return False
    except FileNotFoundError:
        print("✗ pip not found. Please ensure Python is installed correctly.")
        return False

    return True


def verify_installation():
    """Verify that critical packages are installed correctly"""
    print("\nVerifying installations...")

    packages_to_check = [
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
        ("PyQt5", "PyQt5"),
        ("mediapipe", "mediapipe"),
        ("tensorflow", "tensorflow"),
    ]

    for package_import, package_name in packages_to_check:
        try:
            __import__(package_import)
            print(f"✓ {package_name} is available")
        except ImportError:
            print(f"✗ {package_name} is not available")
            return False

    return True


def main():
    """Main setup function"""
    print("AI-Powered Adaptive Dashboard System - Environment Setup")
    print("=" * 60)

    # Check if running in a virtual environment
    in_venv = (
        hasattr(sys, "real_prefix") or
        (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    )

    if not in_venv:
        print("⚠️  Warning: Not running in a virtual environment")
        print("It's recommended to create a virtual environment before installation")
        response = input("Continue anyway? (y/n): ")
        if response.lower() not in ["y", "yes"]:
            print("Setup cancelled.")
            return

    success = True

    # Install requirements
    if not install_requirements():
        success = False

    # Verify installations
    if not verify_installation():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("✓ Setup completed successfully!")
        print("You can now run the dashboard system with: python main.py")
    else:
        print("✗ Setup completed with errors. Please check the messages above.")
        print("Try installing missing packages manually with:")
        print("pip install -r requirements.txt")

    return success


if __name__ == "__main__":
    main()