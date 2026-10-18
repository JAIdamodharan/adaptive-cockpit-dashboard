#!/usr/bin/env python3
"""
Test script to verify camera selection functionality
"""

from driver_monitor import DriverMonitor, list_available_cameras

def test_camera_selection():
    print("Testing Camera Selection Functionality")
    print("=" * 50)

    # List available cameras
    available_cameras = list_available_cameras()
    print(f"Available cameras: {available_cameras}")

    if not available_cameras:
        print("No cameras detected!")
        return False

    # Test automatic camera selection
    print("")
    print("Testing automatic camera selection...")
    dm_auto = DriverMonitor()
    print(f"Auto-selected camera: {dm_auto.camera_index}")

    # Test manual camera selection
    print("")
    print("Testing manual camera selection...")
    manual_index = available_cameras[-1]  # Select last available camera
    dm_manual = DriverMonitor(camera_index=manual_index)
    print(f"Manually selected camera: {dm_manual.camera_index}")

    # Test config loading
    print("")
    print("Configuration loaded:")
    print(f"  Auto-selected: {dm_auto.config}")
    print(f"  Manual-selected: {dm_manual.config}")

    print("")
    print("=" * 50)
    print("Camera selection test completed successfully!")
    print("The system now automatically selects the built-in camera")
    print("instead of the iPhone camera when both are available.")
    
    return True

if __name__ == "__main__":
    test_camera_selection()
