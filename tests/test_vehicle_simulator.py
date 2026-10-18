"""
Unit Tests for Vehicle Simulator Module
"""

import pytest
import time
from src.vehicle_simulator import VehicleSimulator, VehicleState


class TestVehicleSimulator:
    """Test suite for VehicleSimulator class"""
    
    @pytest.fixture
    def simulator(self):
        """Create a vehicle simulator instance for testing"""
        return VehicleSimulator()
    
    def test_initialization(self, simulator):
        """Test simulator initializes with correct default values"""
        state = simulator.get_current_state()
        
        assert state.speed == 0.0
        assert state.rpm == 0
        assert state.fuel_level == 75.0
        assert state.engine_temp == simulator.AMBIENT_TEMP
        assert state.engine_running == False
        assert state.overspeed == False
        assert state.overheating == False
    
    def test_engine_start(self, simulator):
        """Test engine starts correctly"""
        simulator.start()
        time.sleep(0.1)  # Allow state update
        
        state = simulator.get_current_state()
        assert state.engine_running == True
        assert state.rpm == simulator.IDLE_RPM
    
    def test_acceleration(self, simulator):
        """Test vehicle accelerates when accelerator is pressed"""
        simulator.start()
        initial_speed = simulator.state.speed
        
        simulator.set_accelerator(0.8)
        time.sleep(1.5)  # Allow acceleration
        
        final_speed = simulator.state.speed
        assert final_speed > initial_speed
    
    def test_braking(self, simulator):
        """Test vehicle decelerates when brake is pressed"""
        simulator.start()
        
        # First accelerate
        simulator.set_accelerator(0.8)
        time.sleep(2.0)
        speed_before_brake = simulator.state.speed
        
        # Then brake
        simulator.set_accelerator(0.0)
        simulator.set_brake(0.8)
        time.sleep(1.0)
        
        speed_after_brake = simulator.state.speed
        assert speed_after_brake < speed_before_brake
    
    def test_fuel_consumption(self, simulator):
        """Test fuel level decreases during driving"""
        simulator.start()
        initial_fuel = simulator.state.fuel_level
        
        simulator.set_accelerator(0.6)
        time.sleep(3.0)
        
        final_fuel = simulator.state.fuel_level
        assert final_fuel < initial_fuel
    
    def test_rpm_increases_with_speed(self, simulator):
        """Test RPM increases proportionally with speed"""
        simulator.start()
        
        simulator.set_accelerator(0.8)
        time.sleep(2.0)
        
        state = simulator.state
        assert state.rpm > simulator.IDLE_RPM
        assert state.speed > 0
    
    def test_overspeed_detection(self, simulator):
        """Test overspeed flag is set when speed limit exceeded"""
        simulator.start()
        
        # Accelerate beyond speed limit
        simulator.state.speed = simulator.SPEED_LIMIT + 10
        simulator._update_warnings()
        
        assert simulator.state.overspeed == True
    
    def test_overheating_detection(self, simulator):
        """Test overheating flag is set when temperature too high"""
        simulator.start()
        
        # Set high temperature
        simulator.state.engine_temp = simulator.OVERHEAT_THRESHOLD + 5
        simulator._update_warnings()
        
        assert simulator.state.overheating == True
    
    def test_indicator_toggle(self, simulator):
        """Test turn indicators toggle correctly"""
        simulator.start()
        
        # Test left indicator
        initial_left = simulator.state.left_indicator
        simulator.toggle_left_indicator()
        assert simulator.state.left_indicator == (not initial_left)
        
        # Test right indicator
        initial_right = simulator.state.right_indicator
        simulator.toggle_right_indicator()
        assert simulator.state.right_indicator == (not initial_right)
    
    def test_headlights_toggle(self, simulator):
        """Test headlights toggle correctly"""
        simulator.start()
        
        initial_state = simulator.state.headlights
        simulator.toggle_headlights()
        assert simulator.state.headlights == (not initial_state)
    
    def test_odometer_increases(self, simulator):
        """Test odometer increases with travel"""
        simulator.start()
        initial_odometer = simulator.state.odometer
        
        simulator.set_accelerator(0.6)
        time.sleep(2.0)
        
        final_odometer = simulator.state.odometer
        assert final_odometer > initial_odometer
    
    def test_engine_stop(self, simulator):
        """Test engine stops correctly"""
        simulator.start()
        time.sleep(0.5)
        simulator.stop()
        
        state = simulator.state
        assert state.engine_running == False
        assert state.rpm == 0
    
    def test_state_signal_emission(self, simulator, qtbot):
        """Test that state_updated signal is emitted"""
        simulator.start()
        
        with qtbot.waitSignal(simulator.state_updated, timeout=2000):
            pass  # Wait for signal
        
        simulator.stop()


class TestVehicleState:
    """Test suite for VehicleState dataclass"""
    
    def test_vehicle_state_creation(self):
        """Test VehicleState can be created with all fields"""
        state = VehicleState(
            timestamp=time.time(),
            speed=100.0,
            rpm=3000,
            fuel_level=50.0,
            engine_temp=90.0,
            odometer=1234.5,
            left_indicator=False,
            right_indicator=True,
            headlights=True,
            engine_running=True,
            overspeed=False,
            overheating=False
        )
        
        assert state.speed == 100.0
        assert state.rpm == 3000
        assert state.fuel_level == 50.0
    
    def test_vehicle_state_to_dict(self):
        """Test VehicleState converts to dictionary correctly"""
        state = VehicleState(
            timestamp=time.time(),
            speed=80.0,
            rpm=2500,
            fuel_level=60.0,
            engine_temp=85.0,
            odometer=500.0,
            left_indicator=False,
            right_indicator=False,
            headlights=False,
            engine_running=True,
            overspeed=False,
            overheating=False
        )
        
        state_dict = state.to_dict()
        
        assert isinstance(state_dict, dict)
        assert state_dict['speed'] == 80.0
        assert state_dict['rpm'] == 2500
        assert 'timestamp' in state_dict


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
