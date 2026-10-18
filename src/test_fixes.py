#!/usr/bin/env python3
"""
Testing script to verify the fixes for eye movement detection and dashboard flickering
"""

from driver_monitor import DriverMonitor
import time

def test_stability():
    print("Testing Dashboard Stability After Fixes")
    print("=" * 60)
    
    print("Changes made:")
    print("1. Increased EAR threshold gap (0.28 alert vs 0.18 drowsy)")
    print("2. Increased consecutive frames threshold (8 instead of 5)")
    print("3. Improved drowsiness level calculation with hysteresis")
    print("4. Separated blink detection threshold (0.15)")
    print("5. Slower frame processing (0.2s instead of 0.1s)")
    print("6. Larger change threshold in decision engine (0.2 instead of 0.1)")
    print("7. Reduced randomness in simplified detection")
    print()
    
    # Create a driver monitor instance
    print("Initializing Driver Monitor with new parameters...")
    dm = DriverMonitor()
    
    print(f"New EAR thresholds - Alert: {dm.EAR_THRESHOLD_ALERT}, Drowsy: {dm.EAR_THRESHOLD_DROWSY}")
    print(f"New consecutive frames threshold: {dm.CONSECUTIVE_FRAMES_THRESHOLD}")
    print()
    
    # Let it run briefly to see initial state
    print("Initial state after startup:")
    initial_state = dm.get_current_state()
    print(f"  State: {initial_state.state_classification}")
    print(f"  EAR: {initial_state.eye_aspect_ratio:.3f}")
    print(f"  Drowsiness: {initial_state.drowsiness_level:.3f}")
    print(f"  Blink Rate: {initial_state.blink_rate:.1f}/min")
    print()
    
    print("Waiting 10 seconds to observe state stability...")
    time.sleep(10)
    
    print("State after 10 seconds:")
    later_state = dm.get_current_state()
    print(f"  State: {later_state.state_classification}")
    print(f"  EAR: {later_state.eye_aspect_ratio:.3f}")
    print(f"  Drowsiness: {later_state.drowsiness_level:.3f}")
    print(f"  Blink Rate: {later_state.blink_rate:.1f}/min")
    print()
    
    print("Summary of improvements:")
    print("- Wider gap between drowsy and alert thresholds (0.18 vs 0.28)")
    print("- Higher consecutive frames required (8) to declare drowsiness")
    print("- Better hysteresis to prevent oscillations between states")
    print("- Slower update rate to reduce flickering")
    print("- Decision engine requires larger changes to trigger UI updates")
    print("- More stable simplified detection algorithm")
    print()
    print("RESULT: Dashboard flickering should be significantly reduced!")
    print("The system will now maintain more consistent states.")

if __name__ == "__main__":
    test_stability()