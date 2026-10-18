"""
Driving Behavior Analysis Module
Analyzes driving patterns to calculate risk indices and behavior classification
"""

import time
import logging
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
from dataclasses import dataclass
from collections import deque
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class BehaviorMetrics:
    """Data class for driving behavior metrics"""
    timestamp: float
    aggression_score: float  # 0.0 to 1.0
    stability_score: float  # 0.0 to 1.0
    risk_index: float  # 0.0 to 1.0
    behavior_classification: str  # safe, aggressive, risky
    
    # Component metrics
    rapid_acceleration_count: int
    hard_braking_count: int
    overspeed_duration: float  # seconds
    speed_variance: float
    
    # Recommendations
    alert_required: bool
    alert_message: str


class BehaviorAnalyzer(QObject):
    """
    Analyzes driving behavior patterns and calculates risk metrics
    """
    
    # Signals
    behavior_updated = pyqtSignal(object)  # Emits BehaviorMetrics
    
    # Analysis parameters
    ANALYSIS_WINDOW = 30.0  # seconds
    RAPID_ACCEL_THRESHOLD = 10.0  # km/h per second
    HARD_BRAKE_THRESHOLD = 15.0  # km/h per second
    SPEED_LIMIT = 120.0  # km/h
    
    # Risk weights
    AGGRESSION_WEIGHT = 0.4
    INSTABILITY_WEIGHT = 0.3
    OVERSPEED_WEIGHT = 0.3
    
    def __init__(self):
        super().__init__()
        
        # Historical data storage
        self.speed_history = deque(maxlen=300)  # 30 seconds at 0.5s intervals
        self.acceleration_events = deque(maxlen=50)
        self.braking_events = deque(maxlen=50)
        self.overspeed_periods = deque(maxlen=50)
        
        # Previous speed for acceleration calculation
        self.previous_speed = 0.0
        self.previous_timestamp = time.time()
        
        # Current metrics
        self.current_metrics = BehaviorMetrics(
            timestamp=time.time(),
            aggression_score=0.0,
            stability_score=1.0,
            risk_index=0.0,
            behavior_classification="safe",
            rapid_acceleration_count=0,
            hard_braking_count=0,
            overspeed_duration=0.0,
            speed_variance=0.0,
            alert_required=False,
            alert_message=""
        )
        
        # Overspeed tracking
        self.overspeed_start_time = None
        self.total_overspeed_duration = 0.0
        
        logger.info("Behavior Analyzer initialized")
    
    def process_vehicle_data(self, vehicle_state):
        """
        Process incoming vehicle data and update behavior metrics
        
        Args:
            vehicle_state: VehicleState object from vehicle simulator
        """
        current_time = time.time()
        current_speed = vehicle_state.speed
        
        # Store speed in history
        self.speed_history.append({
            'timestamp': current_time,
            'speed': current_speed
        })
        
        # Calculate acceleration
        if len(self.speed_history) >= 2:
            time_delta = current_time - self.previous_timestamp
            if time_delta > 0:
                acceleration = (current_speed - self.previous_speed) / time_delta
                
                # Detect rapid acceleration
                if acceleration > self.RAPID_ACCEL_THRESHOLD:
                    self.acceleration_events.append({
                        'timestamp': current_time,
                        'magnitude': acceleration
                    })
                    logger.debug(f"Rapid acceleration detected: {acceleration:.2f} km/h/s")
                
                # Detect hard braking
                if acceleration < -self.HARD_BRAKE_THRESHOLD:
                    self.braking_events.append({
                        'timestamp': current_time,
                        'magnitude': abs(acceleration)
                    })
                    logger.debug(f"Hard braking detected: {abs(acceleration):.2f} km/h/s")
        
        # Track overspeed duration
        if current_speed > self.SPEED_LIMIT:
            if self.overspeed_start_time is None:
                self.overspeed_start_time = current_time
        else:
            if self.overspeed_start_time is not None:
                overspeed_duration = current_time - self.overspeed_start_time
                self.overspeed_periods.append({
                    'timestamp': current_time,
                    'duration': overspeed_duration
                })
                self.total_overspeed_duration += overspeed_duration
                self.overspeed_start_time = None
        
        # Update previous values
        self.previous_speed = current_speed
        self.previous_timestamp = current_time
        
        # Calculate metrics
        self._calculate_metrics(current_time)
        
        # Emit updated metrics
        self.behavior_updated.emit(self.current_metrics)
    
    def _calculate_metrics(self, current_time: float):
        """Calculate all behavior metrics"""
        # Clean old data
        self._clean_old_data(current_time)
        
        # Calculate aggression score
        aggression_score = self._calculate_aggression_score(current_time)
        
        # Calculate stability score
        stability_score = self._calculate_stability_score()
        
        # Calculate overspeed contribution
        overspeed_contribution = self._calculate_overspeed_contribution(current_time)
        
        # Calculate overall risk index
        risk_index = (
            aggression_score * self.AGGRESSION_WEIGHT +
            (1.0 - stability_score) * self.INSTABILITY_WEIGHT +
            overspeed_contribution * self.OVERSPEED_WEIGHT
        )
        
        # Classify behavior
        behavior_classification = self._classify_behavior(
            risk_index, aggression_score, stability_score
        )
        
        # Determine if alert is needed
        alert_required, alert_message = self._generate_alert(
            behavior_classification, risk_index, aggression_score
        )
        
        # Calculate speed variance
        speed_variance = self._calculate_speed_variance()
        
        # Update current metrics
        self.current_metrics = BehaviorMetrics(
            timestamp=current_time,
            aggression_score=aggression_score,
            stability_score=stability_score,
            risk_index=risk_index,
            behavior_classification=behavior_classification,
            rapid_acceleration_count=len(self.acceleration_events),
            hard_braking_count=len(self.braking_events),
            overspeed_duration=self._get_recent_overspeed_duration(current_time),
            speed_variance=speed_variance,
            alert_required=alert_required,
            alert_message=alert_message
        )
    
    def _clean_old_data(self, current_time: float):
        """Remove data older than analysis window"""
        cutoff_time = current_time - self.ANALYSIS_WINDOW
        
        # Clean acceleration events
        self.acceleration_events = deque(
            [e for e in self.acceleration_events if e['timestamp'] > cutoff_time],
            maxlen=50
        )
        
        # Clean braking events
        self.braking_events = deque(
            [e for e in self.braking_events if e['timestamp'] > cutoff_time],
            maxlen=50
        )
        
        # Clean overspeed periods
        self.overspeed_periods = deque(
            [e for e in self.overspeed_periods if e['timestamp'] > cutoff_time],
            maxlen=50
        )
    
    def _calculate_aggression_score(self, current_time: float) -> float:
        """
        Calculate aggression score based on acceleration and braking events
        Returns: 0.0 (calm) to 1.0 (aggressive)
        """
        # Count recent events
        accel_count = len(self.acceleration_events)
        brake_count = len(self.braking_events)
        
        # Calculate event frequency (events per minute)
        accel_frequency = (accel_count / self.ANALYSIS_WINDOW) * 60.0
        brake_frequency = (brake_count / self.ANALYSIS_WINDOW) * 60.0
        
        # Normalize to 0-1 scale (assuming 3+ events per minute is highly aggressive)
        accel_score = min(1.0, accel_frequency / 3.0)
        brake_score = min(1.0, brake_frequency / 3.0)
        
        # Combined aggression score
        aggression_score = (accel_score + brake_score) / 2.0
        
        return aggression_score
    
    def _calculate_stability_score(self) -> float:
        """
        Calculate stability score based on speed variance
        Returns: 0.0 (unstable) to 1.0 (stable)
        """
        if len(self.speed_history) < 10:
            return 1.0  # Insufficient data, assume stable
        
        # Get recent speeds
        speeds = [entry['speed'] for entry in self.speed_history]
        
        # Calculate variance
        speed_variance = np.var(speeds)
        
        # Normalize to 0-1 scale (assuming variance >100 is unstable)
        # Higher variance = lower stability
        stability_score = max(0.0, 1.0 - (speed_variance / 100.0))
        
        return stability_score
    
    def _calculate_overspeed_contribution(self, current_time: float) -> float:
        """
        Calculate overspeed contribution to risk
        Returns: 0.0 to 1.0
        """
        # Get total overspeed duration in analysis window
        overspeed_duration = self._get_recent_overspeed_duration(current_time)
        
        # Normalize to 0-1 scale (>15 seconds of overspeed is maximum risk)
        overspeed_score = min(1.0, overspeed_duration / 15.0)
        
        return overspeed_score
    
    def _get_recent_overspeed_duration(self, current_time: float) -> float:
        """Get total overspeed duration in recent window"""
        recent_duration = sum(
            period['duration'] 
            for period in self.overspeed_periods
        )
        
        # Add current overspeed period if ongoing
        if self.overspeed_start_time is not None:
            recent_duration += (current_time - self.overspeed_start_time)
        
        return recent_duration
    
    def _calculate_speed_variance(self) -> float:
        """Calculate speed variance for reporting"""
        if len(self.speed_history) < 2:
            return 0.0
        
        speeds = [entry['speed'] for entry in self.speed_history]
        return float(np.var(speeds))
    
    def _classify_behavior(
        self, 
        risk_index: float, 
        aggression_score: float, 
        stability_score: float
    ) -> str:
        """
        Classify driving behavior with hysteresis to prevent rapid switching
        Returns: safe, aggressive, risky
        """
        # Use a class attribute to maintain the current state for hysteresis
        if not hasattr(self, '_current_behavior_state'):
            self._current_behavior_state = "safe"  # Start with safe state
        
        # Add hysteresis to prevent rapid switching between states
        current_state = self._current_behavior_state
        
        if current_state == "risky":
            # To exit risky state, need to be significantly safer
            if risk_index < 0.4 and stability_score > 0.5:
                self._current_behavior_state = "moderate"
        elif current_state == "aggressive":
            # To exit aggressive state, need to be significantly calmer
            if aggression_score < 0.4:
                self._current_behavior_state = "moderate"
        elif current_state == "moderate":
            if risk_index > 0.7 or stability_score < 0.3:
                self._current_behavior_state = "risky"
            elif aggression_score > 0.7:
                self._current_behavior_state = "aggressive"
            elif risk_index < 0.2 and stability_score > 0.7:
                self._current_behavior_state = "safe"
        else:  # safe
            if risk_index > 0.5 or stability_score < 0.5:
                self._current_behavior_state = "moderate"
            elif aggression_score > 0.5:
                self._current_behavior_state = "moderate"
        
        return self._current_behavior_state
    
    def _generate_alert(
        self, 
        behavior_classification: str, 
        risk_index: float, 
        aggression_score: float
    ) -> tuple:
        """
        Generate alert if needed
        Returns: (alert_required: bool, alert_message: str)
        """
        if behavior_classification == "risky":
            return True, "⚠️ Risky driving behavior detected. Please drive carefully."
        elif behavior_classification == "aggressive":
            return True, "⚠️ Aggressive driving detected. Please maintain calm driving."
        elif risk_index > 0.7:
            return True, "🚨 High risk index! Reduce speed and drive safely."
        else:
            return False, ""
    
    def get_current_metrics(self) -> BehaviorMetrics:
        """Get current behavior metrics"""
        return self.current_metrics
    
    def reset_metrics(self):
        """Reset all metrics and history"""
        self.speed_history.clear()
        self.acceleration_events.clear()
        self.braking_events.clear()
        self.overspeed_periods.clear()
        self.total_overspeed_duration = 0.0
        self.overspeed_start_time = None
        logger.info("Behavior metrics reset")
