
import sys
import logging
print("Testing imports...")
try:
    import cv2
    print("cv2 imported")
    import numpy as np
    print("numpy imported")
    import mediapipe as mp
    print("mediapipe imported")
    import tensorflow as tf
    print("tensorflow imported")
    from PyQt5.QtWidgets import QApplication
    print("PyQt5 imported")
    print("SUCCESS: All core libraries imported")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
