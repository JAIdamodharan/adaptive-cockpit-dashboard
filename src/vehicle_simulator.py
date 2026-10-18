"""
Vehicle Data Simulator Module
Generates realistic real-time vehicle parameters with physics-based behavior
"""

import random
import time
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VehicleState:
    """Data class representing complete vehicle state"""
    timestamp: float
    speed: float  # km/h
    rpm: int  # revolutions per minute
    gear: str  # P, N, R, 1-6
    fuel_level: float  # percentage (0-100)
    engine_temp: float  # Celsius
    odometer: float  # km
    left_indicator: bool
    right_indicator: bool
    headlights: bool
    engine_running: bool
    overspeed: bool
    overheating: bool
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


class VehicleSimulator(QObject):
    """
    Simulates realistic vehicle behavior with physics-based parameter generation
    """
    
    # Signals
    state_updated = pyqtSignal(object)  # Emits VehicleState
    
    # Simulation constants
    MAX_SPEED = 200.0  # km/h
    MAX_RPM = 8000
    IDLE_RPM = 800
    SPEED_LIMIT = 120.0  # km/h
    OVERHEAT_THRESHOLD = 110.0  # Celsius
    
    # Physics constants
    ACCELERATION_RATE = 5.0  # km/h per second
    BRAKE_DECELERATION = 15.0  # km/h per second
    NATURAL_DECELERATION = 2.0  # km/h per second
    FUEL_CONSUMPTION_BASE = 0.01  # % per second at idle
    FUEL_CONSUMPTION_SPEED_FACTOR = 0.0001  # % per km/h per second
    ENGINE_HEATING_RATE = 0.5  # Celsius per second
    ENGINE_COOLING_RATE = 0.3  # Celsius per second
    AMBIENT_TEMP = 25.0  # Celsius
    
    def __init__(self):
        super().__init__()
        
        # Current state
        self.state = VehicleState(
            timestamp=time.time(),
            speed=0.0,
            rpm=0,
            gear='P',
            fuel_level=75.0,
            engine_temp=self.AMBIENT_TEMP,
            odometer=0.0,
            left_indicator=False,
            right_indicator=False,
            headlights=False,
            engine_running=False,
            overspeed=False,
            overheating=False
        )
        
        # Input controls
        self.accelerator = 0.0  # 0.0 to 1.0
        self.brake = 0.0  # 0.0 to 1.0
        self.parked = True  # Start in PARK

        # Update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_simulation)
        self.update_interval = 500  # ms (0.5 second)

        # Last update time for delta calculations
        self.last_update_time = time.time()

        logger.info("Vehicle Simulator initialized")
    
    def start(self):
        """Start the vehicle simulation"""
        self.state.engine_running = True
        self.state.rpm = self.IDLE_RPM
        self.last_update_time = time.time()
        self.timer.start(self.update_interval)
        logger.info("Vehicle engine started")
    
    def stop(self):
        """Stop the vehicle simulation"""
        self.timer.stop()
        self.state.engine_running = False
        self.state.rpm = 0
        logger.info("Vehicle engine stopped")
    
    def set_accelerator(self, value: float):
        """Set accelerator pedal position (0.0 to 1.0). Ignored while parked."""
        if self.parked:
            return  # Cannot accelerate while in PARK
        self.accelerator = max(0.0, min(1.0, value))

    def set_brake(self, value: float):
        """Set brake pedal position (0.0 to 1.0)"""
        self.brake = max(0.0, min(1.0, value))

    def engage_park(self):
        """Engage PARK gear: stop the vehicle and lock drive inputs."""
        self.parked = True
        self.accelerator = 0.0
        self.brake = 1.0
        self.state.gear = 'P'
        logger.info("PARK engaged")

    def disengage_park(self):
        """Release PARK gear so the vehicle can be driven."""
        self.parked = False
        self.brake = 0.0
        self.state.gear = 'N'
        logger.info("PARK disengaged")
    
    def toggle_left_indicator(self):
        """Toggle left turn indicator"""
        self.state.left_indicator = not self.state.left_indicator
        if self.state.left_indicator:
            self.state.right_indicator = False
    
    def toggle_right_indicator(self):
        """Toggle right turn indicator"""
        self.state.right_indicator = not self.state.right_indicator
        if self.state.right_indicator:
            self.state.left_indicator = False
    
    def toggle_headlights(self):
        """Toggle headlights"""
        self.state.headlights = not self.state.headlights
    
    def _update_simulation(self):
        """Update all vehicle parameters based on physics simulation"""
        if not self.state.engine_running:
            return
        
        # Calculate time delta
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time
        
        # Update speed
        self._update_speed(dt)
        
        # Update RPM
        self._update_rpm()
        
        # Update fuel level
        self._update_fuel(dt)
        
        # Update engine temperature
        self._update_engine_temperature(dt)
        
        # Update odometer
        self._update_odometer(dt)
        
        # Update warning flags
        self._update_warnings()
        
        # Update timestamp
        self.state.timestamp = current_time
        
        # Emit updated state
        self.state_updated.emit(self.state)
    
    def _update_speed(self, dt: float):
        """Update vehicle speed based on inputs"""
        if self.parked:
            # Hold at zero while parked
            self.state.speed = 0.0
            return
        if self.brake > 0.1:
            deceleration = self.BRAKE_DECELERATION * self.brake
            self.state.speed = max(0.0, self.state.speed - deceleration * dt)
        elif self.accelerator > 0.1:
            acceleration = self.ACCELERATION_RATE * self.accelerator
            self.state.speed = min(self.MAX_SPEED, self.state.speed + acceleration * dt)
        else:
            self.state.speed = max(0.0, self.state.speed - self.NATURAL_DECELERATION * dt)
    
    # Gear thresholds (upper speed boundary in km/h for each gear)
    GEAR_SPEED_THRESHOLDS = [
        (0,   10,  1),
        (10,  30,  2),
        (30,  55,  3),
        (55,  85,  4),
        (85,  120, 5),
        (120, 200, 6),
    ]

    def _update_rpm(self):
        """Update RPM based on speed and calculate current gear"""
        if self.parked:
            self.state.rpm = self.IDLE_RPM if self.state.engine_running else 0
            self.state.gear = 'P'
            return

        if self.state.speed < 1.0:
            # Stationary but not parked -> Neutral
            self.state.rpm = self.IDLE_RPM if self.state.engine_running else 0
            self.state.gear = 'N'
            return

        # Determine gear from speed
        current_gear = 1
        for low, high, gear in self.GEAR_SPEED_THRESHOLDS:
            if low <= self.state.speed < high:
                current_gear = gear
                break
        else:
            current_gear = 6  # top gear

        self.state.gear = str(current_gear)

        # RPM calculation using gear ratio (higher gear = lower RPM at same speed)
        gear_ratios = {1: 3.5, 2: 2.1, 3: 1.4, 4: 1.0, 5: 0.8, 6: 0.65}
        ratio = gear_ratios.get(current_gear, 1.0)
        rpm_from_speed = (self.state.speed / 100.0) * ratio * 2500
        self.state.rpm = int(max(self.IDLE_RPM, min(self.MAX_RPM, rpm_from_speed)))
    
    def _update_fuel(self, dt: float):
        """Update fuel level based on consumption"""
        # Base consumption
        consumption = self.FUEL_CONSUMPTION_BASE * dt
        
        # Speed-dependent consumption
        consumption += self.FUEL_CONSUMPTION_SPEED_FACTOR * self.state.speed * dt
        
        # Acceleration-dependent consumption
        if self.accelerator > 0.5:
            consumption *= 1.5
        
        self.state.fuel_level = max(0.0, self.state.fuel_level - consumption)
    
    def _update_engine_temperature(self, dt: float):
        """Update engine temperature"""
        # Target temperature based on engine load
        if self.state.rpm > 4000 or self.state.speed > 100:
            target_temp = 100.0 + (self.state.rpm - 4000) / 200.0
        else:
            target_temp = 85.0
        
        # Heat up or cool down toward target
        if self.state.engine_temp < target_temp:
            self.state.engine_temp += self.ENGINE_HEATING_RATE * dt
        else:
            self.state.engine_temp -= self.ENGINE_COOLING_RATE * dt
        
        # Clamp to reasonable range
        self.state.engine_temp = max(self.AMBIENT_TEMP, 
                                     min(130.0, self.state.engine_temp))
    
    def _update_odometer(self, dt: float):
        """Update odometer reading"""
        # Distance = speed * time (convert km/h to km)
        distance_km = (self.state.speed / 3600.0) * dt
        self.state.odometer += distance_km
    
    def _update_warnings(self):
        """Update warning flags"""
        self.state.overspeed = self.state.speed > self.SPEED_LIMIT
        self.state.overheating = self.state.engine_temp > self.OVERHEAT_THRESHOLD
    
    def get_current_state(self) -> VehicleState:
        """Get current vehicle state"""
        return self.state
    
    def simulate_random_driving(self):
        """Simulate random driving behavior for testing"""
        # Random acceleration/braking
        if random.random() < 0.3:
            self.set_accelerator(random.uniform(0.3, 0.9))
            self.set_brake(0.0)
        elif random.random() < 0.15:
            self.set_accelerator(0.0)
            self.set_brake(random.uniform(0.3, 0.8))
        else:
            # Maintain current speed
            if self.state.speed > 80:
                self.set_accelerator(0.4)
            else:
                self.set_accelerator(0.6)
            self.set_brake(0.0)
