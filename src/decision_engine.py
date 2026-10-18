"""
Adaptive Decision Engine Module
Rule-based system that determines UI adaptations and alerts based on driver/vehicle/behavior state
"""

import logging
import time
from PyQt5.QtCore import QObject, pyqtSignal
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class UIComplexity(Enum):
    """Dashboard complexity levels"""
    FULL = "full"
    REDUCED = "reduced"
    MINIMAL = "minimal"


class ColorTheme(Enum):
    """Dashboard color themes"""
    STANDARD = "standard"
    CALM = "calm"
    ALERT = "alert"
    DANGER = "danger"


@dataclass
class UIAdaptation:
    """Data class for UI adaptation parameters"""
    complexity: UIComplexity
    color_theme: ColorTheme
    brightness: float  # 0.0 to 1.0
    emphasize_speed: bool
    emphasize_warnings: bool
    show_risk_meter: bool
    soft_colors: bool
    reason: str  # Explanation for the adaptation


@dataclass
class Alert:
    """Data class for safety alerts"""
    priority: int  # 1 (critical) to 3 (info)
    title: str
    message: str
    icon: str
    duration: int  # seconds (-1 for persistent)
    timestamp: float


class AdaptiveDecisionEngine(QObject):
    """
    Core intelligence module that synthesizes all inputs and determines
    adaptive UI changes and safety alerts
    """
    
    # Signals
    ui_adaptation_required = pyqtSignal(object)  # Emits UIAdaptation
    alert_triggered = pyqtSignal(object)  # Emits Alert
    
    def __init__(self):
        super().__init__()
        
        # Current state from modules
        self.vehicle_state = None
        self.driver_state = None
        self.behavior_state = None
        
        # Current UI adaptation
        self.current_adaptation = UIAdaptation(
            complexity=UIComplexity.FULL,
            color_theme=ColorTheme.STANDARD,
            brightness=1.0,
            emphasize_speed=False,
            emphasize_warnings=False,
            show_risk_meter=True,
            soft_colors=False,
            reason="Normal operating conditions"
        )

        # Alert tracking
        self.active_alerts = []
        self.alert_history = []

        # Debounce: minimum seconds between theme/complexity changes
        self.ADAPTATION_COOLDOWN = 5.0
        self._last_theme_change_time = 0.0
        self._pending_adaptation = None  # candidate waiting for debounce
        self._pending_since = 0.0

        logger.info("Adaptive Decision Engine initialized")
    
    def update_vehicle_state(self, vehicle_state):
        """Update vehicle state from simulator"""
        self.vehicle_state = vehicle_state
        self._evaluate_and_adapt()
    
    def update_driver_state(self, driver_state):
        """Update driver cognitive state from monitor"""
        self.driver_state = driver_state
        self._evaluate_and_adapt()
    
    def update_behavior_state(self, behavior_state):
        """Update driving behavior from analyzer"""
        self.behavior_state = behavior_state
        self._evaluate_and_adapt()
    
    def _evaluate_and_adapt(self):
        """
        Main decision logic: evaluate all states and determine adaptations.
        Theme changes are debounced: the new theme must be requested for at
        least ADAPTATION_COOLDOWN seconds before it is applied.
        """
        if not all([self.vehicle_state, self.driver_state, self.behavior_state]):
            return

        adaptation = self._apply_decision_rules()
        now = time.time()

        # Is this a different theme than what is currently shown?
        theme_changed = (
            adaptation.color_theme != self.current_adaptation.color_theme or
            adaptation.complexity != self.current_adaptation.complexity
        )

        if not theme_changed:
            # Same theme — reset any pending candidate
            self._pending_adaptation = None
            self._pending_since = 0.0
        else:
            # Classify urgency: always allow immediate escalation to DANGER
            is_escalation_to_danger = (
                adaptation.color_theme == ColorTheme.DANGER and
                self.current_adaptation.color_theme != ColorTheme.DANGER
            )

            if is_escalation_to_danger:
                # Apply immediately — safety first
                logger.info(f"UI Adaptation (immediate): {adaptation.reason}")
                self.current_adaptation = adaptation
                self._last_theme_change_time = now
                self._pending_adaptation = None
                self.ui_adaptation_required.emit(adaptation)
            else:
                # Track how long this new theme has been requested
                if (
                    self._pending_adaptation is None or
                    self._pending_adaptation.color_theme != adaptation.color_theme or
                    self._pending_adaptation.complexity != adaptation.complexity
                ):
                    # New candidate — restart the timer
                    self._pending_adaptation = adaptation
                    self._pending_since = now
                else:
                    # Same candidate — check if it has been stable long enough
                    elapsed = now - self._pending_since
                    cooldown_ok = (now - self._last_theme_change_time) >= self.ADAPTATION_COOLDOWN
                    if elapsed >= self.ADAPTATION_COOLDOWN and cooldown_ok:
                        logger.info(f"UI Adaptation: {adaptation.reason}")
                        self.current_adaptation = adaptation
                        self._last_theme_change_time = now
                        self._pending_adaptation = None
                        self.ui_adaptation_required.emit(adaptation)
                    # else: still in debounce — do nothing

        # Generate alerts (not debounced)
        self._generate_alerts()
    
    def _driver_class(self) -> str:
        """Driver state fused with driving behaviour.

        Fatigue signs plus erratic driving (high risk or low stability) are much stronger
        evidence than either alone, so a fatigued driver who also drives badly is
        escalated to drowsy.
        """
        cls = self.driver_state.state_classification
        if cls == "fatigued" and self.behavior_state is not None:
            if (self.behavior_state.risk_index > 0.5
                    or self.behavior_state.stability_score < 0.4):
                return "drowsy"
        return cls

    def _apply_decision_rules(self) -> UIAdaptation:
        """
        Apply rule-based decision logic to determine UI adaptation
        
        Rule Priority (highest to lowest):
        1. Critical safety (drowsy + risky behavior)
        2. Driver drowsiness
        3. Vehicle critical warnings (overheating)
        4. Aggressive/risky driving
        5. Driver stress
        6. Normal operation
        """
        
        # Rule 1: Critical Safety - Drowsy + Risky Behavior
        if (self._driver_class() == "drowsy" and 
            self.behavior_state.risk_index > 0.5):
            return UIAdaptation(
                complexity=UIComplexity.MINIMAL,
                color_theme=ColorTheme.DANGER,
                brightness=0.6,
                emphasize_speed=True,
                emphasize_warnings=True,
                show_risk_meter=False,
                soft_colors=False,
                reason="CRITICAL: Drowsy driver with risky behavior - Minimal UI with speed focus"
            )
        
        # Rule 2: Driver Drowsiness
        if self._driver_class() == "drowsy":
            return UIAdaptation(
                complexity=UIComplexity.MINIMAL,
                color_theme=ColorTheme.DANGER,
                brightness=0.7,
                emphasize_speed=True,
                emphasize_warnings=True,
                show_risk_meter=False,
                soft_colors=False,
                reason="DROWSINESS DETECTED: Critical driver state - Minimize distractions"
            )
        
        # Rule 3: Vehicle Overheating
        if self.vehicle_state.overheating:
            return UIAdaptation(
                complexity=UIComplexity.REDUCED,
                color_theme=ColorTheme.DANGER,
                brightness=1.0,
                emphasize_speed=False,
                emphasize_warnings=True,
                show_risk_meter=False,
                soft_colors=False,
                reason="ENGINE OVERHEATING: Critical vehicle issue - Focus on warnings"
            )
        
        # Rule 4: Severe Overheating (temperature > 120°C)
        if self.vehicle_state.engine_temp > 120.0:
            return UIAdaptation(
                complexity=UIComplexity.MINIMAL,
                color_theme=ColorTheme.DANGER,
                brightness=1.0,
                emphasize_speed=False,
                emphasize_warnings=True,
                show_risk_meter=False,
                soft_colors=False,
                reason="SEVERE OVERHEATING: Engine temp critically high - Emergency mode"
            )
        
        # Rule 5: Aggressive Driving + Overspeed (enhanced)
        if (self.behavior_state.behavior_classification == "aggressive" and 
            self.vehicle_state.overspeed):
            return UIAdaptation(
                complexity=UIComplexity.FULL,
                color_theme=ColorTheme.ALERT,
                brightness=1.0,
                emphasize_speed=True,
                emphasize_warnings=True,
                show_risk_meter=True,
                soft_colors=False,
                reason="AGGRESSIVE + OVERSPEED: High-risk combination - Enhanced monitoring"
            )
        
        # Rule 6: High Risk with Overspeed (even if not aggressive)
        if (self.behavior_state.risk_index > 0.7 and self.vehicle_state.overspeed):
            return UIAdaptation(
                complexity=UIComplexity.FULL,
                color_theme=ColorTheme.ALERT,
                brightness=1.0,
                emphasize_speed=True,
                emphasize_warnings=True,
                show_risk_meter=True,
                soft_colors=False,
                reason="HIGH RISK + OVERSPEED: Reduce speed immediately"
            )
        
        # Rule 7: Risky Behavior (enhanced)
        if self.behavior_state.behavior_classification == "risky":
            return UIAdaptation(
                complexity=UIComplexity.FULL,
                color_theme=ColorTheme.ALERT,
                brightness=0.95,
                emphasize_speed=True,
                emphasize_warnings=True,
                show_risk_meter=True,
                soft_colors=False,
                reason="RISKY DRIVING: Continue monitoring closely - Risk metrics displayed"
            )
        
        # Rule 8: Driver Fatigue (enhanced)
        if self._driver_class() == "fatigued":
            return UIAdaptation(
                complexity=UIComplexity.REDUCED,
                color_theme=ColorTheme.CALM,
                brightness=0.9,
                emphasize_speed=True,
                emphasize_warnings=True,
                show_risk_meter=False,
                soft_colors=True,
                reason="DRIVER FATIGUE: Reduce cognitive load - Softer interface"
            )
        
        # Rule 9: Driver Stress (enhanced)
        if self._driver_class() == "stressed":
            return UIAdaptation(
                complexity=UIComplexity.REDUCED,
                color_theme=ColorTheme.CALM,
                brightness=0.85,
                emphasize_speed=False,
                emphasize_warnings=False,
                show_risk_meter=False,
                soft_colors=True,
                reason="DRIVER STRESS: Reduce visual stimulation - Calming interface"
            )
        
        # Rule 10: Overspeed only (moderate adjustment)
        if self.vehicle_state.overspeed:
            return UIAdaptation(
                complexity=UIComplexity.FULL,
                color_theme=ColorTheme.ALERT,
                brightness=1.0,
                emphasize_speed=True,
                emphasize_warnings=True,
                show_risk_meter=True,
                soft_colors=False,
                reason="OVERSPEED: Reduce to legal limits - Enhanced speed visibility"
            )
        
        # Rule 11: Low Fuel Warning
        if self.vehicle_state.fuel_level < 15.0:
            return UIAdaptation(
                complexity=UIComplexity.FULL,
                color_theme=ColorTheme.ALERT,
                brightness=1.0,
                emphasize_speed=False,
                emphasize_warnings=True,
                show_risk_meter=True,
                soft_colors=False,
                reason="LOW FUEL: Less than 15% remaining - Plan refueling"
            )
        
        # Rule 12: Very Low Fuel
        if self.vehicle_state.fuel_level < 5.0:
            return UIAdaptation(
                complexity=UIComplexity.FULL,
                color_theme=ColorTheme.DANGER,
                brightness=1.0,
                emphasize_speed=False,
                emphasize_warnings=True,
                show_risk_meter=True,
                soft_colors=False,
                reason="CRITICAL FUEL LEVEL: Find gas station immediately"
            )
        
        # Rule 13: High Aggression without overspeed (warning)
        if (self.behavior_state.behavior_classification == "aggressive" and 
            not self.vehicle_state.overspeed):
            return UIAdaptation(
                complexity=UIComplexity.FULL,
                color_theme=ColorTheme.ALERT,
                brightness=0.98,
                emphasize_speed=False,
                emphasize_warnings=True,
                show_risk_meter=True,
                soft_colors=False,
                reason="AGGRESSIVE DRIVING: Dangerous driving pattern detected"
            )
        
        # Default: Normal Operation
        return UIAdaptation(
            complexity=UIComplexity.FULL,
            color_theme=ColorTheme.STANDARD,
            brightness=1.0,
            emphasize_speed=False,
            emphasize_warnings=False,
            show_risk_meter=True,
            soft_colors=False,
            reason="NORMAL: All systems nominal - Full dashboard operational"
        )
    
    # _adaptation_changed removed — debounce logic now lives in _evaluate_and_adapt

    
    def _generate_alerts(self):
        """Generate safety alerts based on current conditions"""
        import time
        
        alerts_to_trigger = []
        
        # Critical: Drowsy driver
        if self._driver_class() == "drowsy":
            if not self._alert_exists("drowsy_driver"):
                alerts_to_trigger.append(Alert(
                    priority=1,
                    title="⚠️ DROWSINESS DETECTED",
                    message="You appear drowsy. Please take a rest break immediately.",
                    icon="warning",
                    duration=-1,  # Persistent
                    timestamp=time.time()
                ))
        
        # Critical: Engine overheating
        if self.vehicle_state.overheating:
            if not self._alert_exists("engine_overheating"):
                alerts_to_trigger.append(Alert(
                    priority=1,
                    title="🔥 ENGINE OVERHEATING",
                    message=f"Engine temperature: {self.vehicle_state.engine_temp:.1f}°C. Pull over safely.",
                    icon="danger",
                    duration=-1,  # Persistent
                    timestamp=time.time()
                ))
        
        # High priority: Risky behavior
        if self.behavior_state.risk_index > 0.7:
            if not self._alert_exists("high_risk"):
                alerts_to_trigger.append(Alert(
                    priority=2,
                    title="⚠️ HIGH RISK DRIVING",
                    message=f"Risk index: {self.behavior_state.risk_index*100:.0f}%. Please drive more carefully.",
                    icon="warning",
                    duration=10,
                    timestamp=time.time()
                ))
        
        # High priority: Aggressive driving
        if self.behavior_state.behavior_classification == "aggressive":
            if not self._alert_exists("aggressive_driving"):
                alerts_to_trigger.append(Alert(
                    priority=2,
                    title="⚠️ AGGRESSIVE DRIVING",
                    message=self.behavior_state.alert_message,
                    icon="warning",
                    duration=8,
                    timestamp=time.time()
                ))
        
        # Medium priority: Overspeed
        if self.vehicle_state.overspeed:
            if not self._alert_exists("overspeed"):
                alerts_to_trigger.append(Alert(
                    priority=2,
                    title="⚠️ SPEED LIMIT EXCEEDED",
                    message=f"Current speed: {self.vehicle_state.speed:.0f} km/h. Limit: 120 km/h",
                    icon="warning",
                    duration=5,
                    timestamp=time.time()
                ))
        
        # Medium priority: Low fuel
        if self.vehicle_state.fuel_level < 15.0:
            if not self._alert_exists("low_fuel"):
                alerts_to_trigger.append(Alert(
                    priority=2,
                    title="⛽ LOW FUEL",
                    message=f"Fuel level: {self.vehicle_state.fuel_level:.1f}%. Find a gas station soon.",
                    icon="info",
                    duration=10,
                    timestamp=time.time()
                ))
        
        # Info: Driver fatigue
        if self._driver_class() == "fatigued":
            if not self._alert_exists("fatigue"):
                alerts_to_trigger.append(Alert(
                    priority=3,
                    title="😴 FATIGUE DETECTED",
                    message="Consider taking a break soon.",
                    icon="info",
                    duration=8,
                    timestamp=time.time()
                ))
        
        # Emit all new alerts
        for alert in alerts_to_trigger:
            logger.info(f"Alert triggered: {alert.title}")
            self.alert_triggered.emit(alert)
            self.active_alerts.append(alert)
            self.alert_history.append(alert)
    
    def _alert_exists(self, alert_type: str) -> bool:
        """Check if alert of given type is already active"""
        # Simple check based on title keywords
        type_keywords = {
            "drowsy_driver": "DROWSINESS",
            "engine_overheating": "OVERHEATING",
            "high_risk": "HIGH RISK",
            "aggressive_driving": "AGGRESSIVE",
            "overspeed": "SPEED LIMIT",
            "low_fuel": "LOW FUEL",
            "fatigue": "FATIGUE"
        }
        
        keyword = type_keywords.get(alert_type, "")
        return any(keyword in alert.title for alert in self.active_alerts)
    
    def dismiss_alert(self, alert: Alert):
        """Dismiss an active alert"""
        if alert in self.active_alerts:
            self.active_alerts.remove(alert)
    
    def get_current_adaptation(self) -> UIAdaptation:
        """Get current UI adaptation"""
        return self.current_adaptation
