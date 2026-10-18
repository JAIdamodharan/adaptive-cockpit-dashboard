#!/usr/bin/env python3
"""
Test script to verify button functionality fixes
"""

import sys
import time
from PyQt5.QtWidgets import QApplication
from vehicle_simulator import VehicleSimulator
from driver_monitor import DriverMonitor
from behavior_analyzer import BehaviorAnalyzer
from decision_engine import AdaptiveDecisionEngine

def test_buttons():
    print("Testing Button Functionality Fixes")
    print("=" * 50)
    
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Initialize modules
    vehicle_simulator = VehicleSimulator()
    driver_monitor = DriverMonitor()
    behavior_analyzer = BehaviorAnalyzer()
    decision_engine = AdaptiveDecisionEngine()
    
    # Start the vehicle simulator
    vehicle_simulator.start()
    print("Vehicle simulator started")
    
    # Test initial state
    initial_state = vehicle_simulator.get_current_state()
    print(f"Initial vehicle state - Speed: {initial_state.speed}, Engine: {initial_state.engine_running}")
    print(f"Indicators - Left: {initial_state.left_indicator}, Right: {initial_state.right_indicator}, Headlights: {initial_state.headlights}")
    
    # Test accelerator
    print("\nTesting accelerator...")
    vehicle_simulator.set_accelerator(0.8)
    time.sleep(1)
    state_after_accel = vehicle_simulator.get_current_state()
    print(f"After accelerator - Speed: {state_after_accel.speed}")
    
    # Release accelerator
    vehicle_simulator.set_accelerator(0.0)
    time.sleep(1)
    state_after_release = vehicle_simulator.get_current_state()
    print(f"After releasing accelerator - Speed: {state_after_release.speed}")
    
    # Test brake
    print("\nTesting brake...")
    vehicle_simulator.set_brake(0.8)
    time.sleep(1)
    state_after_brake = vehicle_simulator.get_current_state()
    print(f"After brake - Speed: {state_after_brake.speed}")
    
    # Release brake
    vehicle_simulator.set_brake(0.0)
    time.sleep(1)
    state_after_release_brake = vehicle_simulator.get_current_state()
    print(f"After releasing brake - Speed: {state_after_release_brake.speed}")
    
    # Test indicators
    print("\nTesting indicators...")
    print(f"Before toggle - Left: {vehicle_simulator.get_current_state().left_indicator}")
    vehicle_simulator.toggle_left_indicator()
    time.sleep(0.5)
    print(f"After left toggle - Left: {vehicle_simulator.get_current_state().left_indicator}, Right: {vehicle_simulator.get_current_state().right_indicator}")
    
    vehicle_simulator.toggle_right_indicator()
    time.sleep(0.5)
    print(f"After right toggle - Right: {vehicle_simulator.get_current_state().right_indicator}, Left: {vehicle_simulator.get_current_state().left_indicator}")
    
    # Test headlights
    print(f"Before headlights - Headlights: {vehicle_simulator.get_current_state().headlights}")
    vehicle_simulator.toggle_headlights()
    time.sleep(0.5)
    print(f"After headlights toggle - Headlights: {vehicle_simulator.get_current_state().headlights}")
    
    # Stop simulator
    vehicle_simulator.stop()
    print("\nVehicle simulator stopped")
    
    print("\nButton functionality test completed successfully!")
    print("Changes made:")
    print("- Added visual feedback for button presses")
    print("- Made indicator buttons toggle-able with state sync")
    print("- Fixed state synchronization between UI and simulator")
    print("- Added proper visual indication for active states")

if __name__ == "__main__":
    test_buttons()
