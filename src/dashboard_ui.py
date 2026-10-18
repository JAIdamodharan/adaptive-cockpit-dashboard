"""
Adaptive Dashboard UI Module
PyQt5-based dynamic dashboard with adaptive interface capabilities
"""

import logging
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QProgressBar, QFrame, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor

from decision_engine import UIComplexity, ColorTheme

logger = logging.getLogger(__name__)


class AdaptiveDashboardUI(QMainWindow):
    """
    Main dashboard window with adaptive interface capabilities
    """

    # Color scheme definitions
    THEMES = {
        ColorTheme.STANDARD: {
            'bg': '#1a1a1a',
            'fg': '#ffffff',
            'accent': '#4CAF50',
            'warning': '#FFC107',
            'danger': '#f44336'
        },
        ColorTheme.CALM: {
            'bg': '#0d1b2a',
            'fg': '#e0fbfc',
            'accent': '#5390d9',
            'warning': '#72b6ff',
            'danger': '#ff8fa3'
        },
        ColorTheme.ALERT: {
            'bg': '#2d1b00',
            'fg': '#ffffff',
            'accent': '#ffa500',
            'warning': '#ff6b00',
            'danger': '#ff0000'
        },
        ColorTheme.DANGER: {
            'bg': '#330000',
            'fg': '#ffffff',
            'accent': '#ff4444',
            'warning': '#ff0000',
            'danger': '#cc0000'
        }
    }

    def __init__(self, vehicle_simulator, driver_monitor, behavior_analyzer, decision_engine):
        super().__init__()

        self.vehicle_simulator = vehicle_simulator
        self.driver_monitor = driver_monitor
        self.behavior_analyzer = behavior_analyzer
        self.decision_engine = decision_engine

        # Current theme and complexity
        self.current_theme = ColorTheme.STANDARD
        self.current_complexity = UIComplexity.FULL

        # Initialize UI
        self._init_ui()

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_dashboard)
        self.update_timer.start(500)  # 0.5s updates

        logger.info("Dashboard UI initialized")

    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("AI-Powered Adaptive Vehicle Dashboard")
        self.setGeometry(100, 100, 1400, 900)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Header
        self.header_label = QLabel("ADAPTIVE DASHBOARD")
        self.header_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.header_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.header_label)

        # Content layout (grid)
        content_layout = QGridLayout()
        main_layout.addLayout(content_layout)

        # Left: Vehicle instruments
        self.instruments_group = self._create_instruments_panel()
        content_layout.addWidget(self.instruments_group, 0, 0, 2, 1)

        # Center: Driver and behavior
        self.driver_state_group = self._create_driver_state_panel()
        content_layout.addWidget(self.driver_state_group, 0, 1)

        self.behavior_group = self._create_behavior_panel()
        content_layout.addWidget(self.behavior_group, 1, 1)

        # Right: Alerts
        self.alerts_group = self._create_alerts_panel()
        content_layout.addWidget(self.alerts_group, 0, 2, 2, 1)

        # Bottom: Control panel
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)

        # Floating alert display
        self.alert_display = QLabel("")
        self.alert_display.setFont(QFont("Arial", 16, QFont.Bold))
        self.alert_display.setAlignment(Qt.AlignCenter)
        self.alert_display.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 0, 0, 180);
                color: white;
                padding: 20px;
                border-radius: 10px;
            }
        """)
        self.alert_display.setParent(self)
        self.alert_display.move(300, 50)  # top center-ish
        self.alert_display.hide()

        # Apply initial theme
        self._apply_theme(self.current_theme)

    # -----------------------------
    # Panel creation methods
    # -----------------------------
    def _create_instruments_panel(self) -> QGroupBox:
        group = QGroupBox("VEHICLE INSTRUMENTS")
        group.setFont(QFont("Arial", 14, QFont.Bold))
        layout = QVBoxLayout()
        
        # Set minimum size to maintain layout consistency
        group.setMinimumSize(300, 400)
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Speedometer
        speed_layout = QHBoxLayout()
        self.speed_label = QLabel("0")
        self.speed_label.setFont(QFont("Arial", 72, QFont.Bold))
        self.speed_label.setAlignment(Qt.AlignCenter)
        speed_layout.addWidget(self.speed_label)

        speed_unit = QLabel("km/h")
        speed_unit.setFont(QFont("Arial", 24))
        speed_unit.setAlignment(Qt.AlignCenter)
        speed_layout.addWidget(speed_unit)
        layout.addLayout(speed_layout)

        # RPM
        rpm_layout = QHBoxLayout()
        rpm_layout.addWidget(QLabel("RPM:"))
        self.rpm_label = QLabel("0")
        self.rpm_label.setFont(QFont("Arial", 32, QFont.Bold))
        rpm_layout.addWidget(self.rpm_label)
        rpm_layout.addStretch()
        layout.addLayout(rpm_layout)

        # Fuel
        fuel_layout = QVBoxLayout()
        fuel_layout.addWidget(QLabel("Fuel Level:"))
        self.fuel_bar = QProgressBar()
        self.fuel_bar.setMaximum(100)
        self.fuel_bar.setMinimumHeight(20)
        self.fuel_bar.setTextVisible(True)
        fuel_layout.addWidget(self.fuel_bar)
        layout.addLayout(fuel_layout)

        # Engine temp
        temp_layout = QVBoxLayout()
        temp_layout.addWidget(QLabel("Engine Temperature:"))
        self.temp_bar = QProgressBar()
        self.temp_bar.setMaximum(130)
        self.temp_bar.setMinimumHeight(20)
        self.temp_bar.setTextVisible(True)
        temp_layout.addWidget(self.temp_bar)
        layout.addLayout(temp_layout)

        # Odometer
        self.odometer_label = QLabel("Odometer: 0.0 km")
        self.odometer_label.setFont(QFont("Arial", 12))
        self.odometer_label.setMinimumHeight(20)
        layout.addWidget(self.odometer_label)

        # Indicators
        indicators_layout = QHBoxLayout()
        self.left_indicator = QLabel("◀")
        self.left_indicator.setFont(QFont("Arial", 24))
        self.left_indicator.setMinimumSize(40, 40)
        indicators_layout.addWidget(self.left_indicator)

        self.headlights_indicator = QLabel("💡")
        self.headlights_indicator.setFont(QFont("Arial", 24))
        self.headlights_indicator.setMinimumSize(40, 40)
        indicators_layout.addWidget(self.headlights_indicator)

        self.right_indicator = QLabel("▶")
        self.right_indicator.setFont(QFont("Arial", 24))
        self.right_indicator.setMinimumSize(40, 40)
        indicators_layout.addWidget(self.right_indicator)
        layout.addLayout(indicators_layout)

        group.setLayout(layout)
        return group

    def _create_driver_state_panel(self) -> QGroupBox:
        group = QGroupBox("DRIVER STATE")
        group.setFont(QFont("Arial", 14, QFont.Bold))
        layout = QVBoxLayout()
        
        # Set minimum size to maintain layout consistency
        group.setMinimumSize(250, 200)
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.driver_state_label = QLabel("State: NORMAL")
        self.driver_state_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.driver_state_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.driver_state_label)

        # Drowsiness
        layout.addWidget(QLabel("Drowsiness Level:"))
        self.drowsiness_bar = QProgressBar()
        self.drowsiness_bar.setMaximum(100)
        self.drowsiness_bar.setMinimumHeight(16)
        layout.addWidget(self.drowsiness_bar)

        self.ear_label = QLabel("Eye Aspect Ratio: 0.30")
        self.ear_label.setMinimumHeight(16)
        layout.addWidget(self.ear_label)
        self.blink_label = QLabel("Blink Rate: 20/min")
        self.blink_label.setMinimumHeight(16)
        layout.addWidget(self.blink_label)
        self.emotion_label = QLabel("Emotion: Calm")
        self.emotion_label.setMinimumHeight(16)
        layout.addWidget(self.emotion_label)

        group.setLayout(layout)
        return group

    def _create_behavior_panel(self) -> QGroupBox:
        group = QGroupBox("DRIVING BEHAVIOR")
        group.setFont(QFont("Arial", 14, QFont.Bold))
        layout = QVBoxLayout()

        self.behavior_label = QLabel("Behavior: SAFE")
        self.behavior_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.behavior_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.behavior_label)

        # Risk
        layout.addWidget(QLabel("Risk Index:"))
        self.risk_bar = QProgressBar()
        self.risk_bar.setMaximum(100)
        layout.addWidget(self.risk_bar)

        # Aggression
        layout.addWidget(QLabel("Aggression Score:"))
        self.aggression_bar = QProgressBar()
        self.aggression_bar.setMaximum(100)
        layout.addWidget(self.aggression_bar)

        # Stability
        layout.addWidget(QLabel("Stability Score:"))
        self.stability_bar = QProgressBar()
        self.stability_bar.setMaximum(100)
        layout.addWidget(self.stability_bar)

        self.events_label = QLabel("Rapid Accel: 0 | Hard Braking: 0")
        layout.addWidget(self.events_label)

        group.setLayout(layout)
        return group

    def _create_alerts_panel(self) -> QGroupBox:
        group = QGroupBox("ALERTS & WARNINGS")
        group.setFont(QFont("Arial", 14, QFont.Bold))
        layout = QVBoxLayout()

        self.alerts_text = QLabel("No active alerts")
        self.alerts_text.setWordWrap(True)
        self.alerts_text.setFont(QFont("Arial", 11))
        layout.addWidget(self.alerts_text)

        warnings_layout = QGridLayout()
        self.overspeed_warning = QLabel("🚨")
        self.overheat_warning = QLabel("🔥")
        self.drowsy_warning = QLabel("😴")

        for i, w in enumerate([self.overspeed_warning, self.overheat_warning, self.drowsy_warning]):
            w.setFont(QFont("Arial", 32))
            w.setAlignment(Qt.AlignCenter)
            w.hide()
        warnings_layout.addWidget(QLabel("Overspeed:"), 0, 0)
        warnings_layout.addWidget(self.overspeed_warning, 0, 1)
        warnings_layout.addWidget(QLabel("Overheating:"), 1, 0)
        warnings_layout.addWidget(self.overheat_warning, 1, 1)
        warnings_layout.addWidget(QLabel("Drowsy:"), 2, 0)
        warnings_layout.addWidget(self.drowsy_warning, 2, 1)

        layout.addLayout(warnings_layout)

        layout.addWidget(QLabel("Current Adaptation:"))
        self.adaptation_label = QLabel("Normal mode")
        self.adaptation_label.setFont(QFont("Arial", 10))
        layout.addWidget(self.adaptation_label)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def _create_control_panel(self) -> QFrame:
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout()
        
        # Set minimum size to maintain layout consistency
        frame.setMinimumHeight(60)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Accelerator
        self.accel_btn = QPushButton("⬆ Accelerate")
        self.accel_btn.setMinimumSize(90, 40)
        self.accel_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.accel_btn.setCheckable(True)  # Make it track press state
        def on_accel_press():
            self.vehicle_simulator.set_accelerator(0.8)
            # Visual feedback
            self.accel_btn.setStyleSheet("background-color: #D32F2F; color: white;")  # Dark red when pressed
        
        def on_accel_release():
            self.vehicle_simulator.set_accelerator(0.0)
            # Restore original color
            self.accel_btn.setStyleSheet("")
        
        self.accel_btn.pressed.connect(on_accel_press)
        self.accel_btn.released.connect(on_accel_release)
        layout.addWidget(self.accel_btn)

        # Brake
        self.brake_btn = QPushButton("⬇ Brake")
        self.brake_btn.setMinimumSize(90, 40)
        self.brake_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.brake_btn.setCheckable(True)  # Make it track press state
        def on_brake_press():
            self.vehicle_simulator.set_brake(0.8)
            # Visual feedback
            self.brake_btn.setStyleSheet("background-color: #D32F2F; color: white;")  # Dark red when pressed
        
        def on_brake_release():
            self.vehicle_simulator.set_brake(0.0)
            # Restore original color
            self.brake_btn.setStyleSheet("")
        
        self.brake_btn.pressed.connect(on_brake_press)
        self.brake_btn.released.connect(on_brake_release)
        layout.addWidget(self.brake_btn)

        # Left indicator - with toggle visual feedback
        self.left_ind_btn = QPushButton("◀ Left Signal")
        self.left_ind_btn.setMinimumSize(80, 40)
        self.left_ind_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.left_ind_btn.setCheckable(True)  # Make it toggle-able
        
        def toggle_left_indicator():
            self.vehicle_simulator.toggle_left_indicator()
            # Get current state and update button appearance
            current_state = self.vehicle_simulator.get_current_state()
            if current_state.left_indicator:
                self.left_ind_btn.setStyleSheet("background-color: #4CAF50; color: white;")
                self.left_ind_btn.setChecked(True)
            else:
                self.left_ind_btn.setStyleSheet("")
                self.left_ind_btn.setChecked(False)
                
        self.left_ind_btn.clicked.connect(toggle_left_indicator)
        layout.addWidget(self.left_ind_btn)

        # Right indicator - with toggle visual feedback  
        self.right_ind_btn = QPushButton("Right Signal ▶")
        self.right_ind_btn.setMinimumSize(80, 40)
        self.right_ind_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.right_ind_btn.setCheckable(True)  # Make it toggle-able
        
        def toggle_right_indicator():
            self.vehicle_simulator.toggle_right_indicator()
            # Get current state and update button appearance
            current_state = self.vehicle_simulator.get_current_state()
            if current_state.right_indicator:
                self.right_ind_btn.setStyleSheet("background-color: #4CAF50; color: white;")
                self.right_ind_btn.setChecked(True)
            else:
                self.right_ind_btn.setStyleSheet("")
                self.right_ind_btn.setChecked(False)
                
        self.right_ind_btn.clicked.connect(toggle_right_indicator)
        layout.addWidget(self.right_ind_btn)

        # Headlights - with toggle visual feedback
        self.lights_btn = QPushButton("💡 Headlights")
        self.lights_btn.setMinimumSize(80, 40)
        self.lights_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.lights_btn.setCheckable(True)  # Make it toggle-able
        
        def toggle_headlights():
            self.vehicle_simulator.toggle_headlights()
            # Get current state and update button appearance
            current_state = self.vehicle_simulator.get_current_state()
            if current_state.headlights:
                self.lights_btn.setStyleSheet("background-color: #FFEB3B; color: black;")
                self.lights_btn.setChecked(True)
            else:
                self.lights_btn.setStyleSheet("")
                self.lights_btn.setChecked(False)
                
        self.lights_btn.clicked.connect(toggle_headlights)
        layout.addWidget(self.lights_btn)

        # Auto Drive
        self.random_btn = QPushButton("Auto Drive")
        self.random_btn.setMinimumSize(90, 40)
        self.random_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.random_btn.clicked.connect(self._toggle_auto_drive)
        layout.addWidget(self.random_btn)

        frame.setLayout(layout)
        return frame

    # -----------------------------
    # Dashboard update methods
    # -----------------------------
    @pyqtSlot()
    def _update_dashboard(self):
        """Update dashboard displays with current data"""
        vehicle_state = self.vehicle_simulator.get_current_state()
        driver_state = self.driver_monitor.get_current_state()
        behavior_state = self.behavior_analyzer.get_current_metrics()

        # Vehicle instruments
        self.speed_label.setText(f"{vehicle_state.speed:.0f}")
        self.rpm_label.setText(f"{vehicle_state.rpm}")
        self.fuel_bar.setValue(int(vehicle_state.fuel_level))
        self.temp_bar.setValue(int(vehicle_state.engine_temp))
        self.odometer_label.setText(f"Odometer: {vehicle_state.odometer:.2f} km")

        # Indicators
        self.left_indicator.setStyleSheet("color: #FF5722;" if vehicle_state.left_indicator else "color: gray;")  # Orange-red when active
        self.right_indicator.setStyleSheet("color: #FF5722;" if vehicle_state.right_indicator else "color: gray;")  # Orange-red when active
        self.headlights_indicator.setStyleSheet("color: #FFEB3B;" if vehicle_state.headlights else "color: gray;")  # Yellow when active

        # Update control buttons to match actual state (in case of external changes)
        if hasattr(self, 'left_ind_btn'):
            if vehicle_state.left_indicator:
                self.left_ind_btn.setStyleSheet("background-color: #4CAF50; color: white;")
                self.left_ind_btn.setChecked(True)
            else:
                self.left_ind_btn.setStyleSheet("")  # Original theme
                self.left_ind_btn.setChecked(False)
                
        if hasattr(self, 'right_ind_btn'):
            if vehicle_state.right_indicator:
                self.right_ind_btn.setStyleSheet("background-color: #4CAF50; color: white;")
                self.right_ind_btn.setChecked(True)
            else:
                self.right_ind_btn.setStyleSheet("")  # Original theme
                self.right_ind_btn.setChecked(False)
                
        if hasattr(self, 'lights_btn'):
            if vehicle_state.headlights:
                self.lights_btn.setStyleSheet("background-color: #FFEB3B; color: black;")
                self.lights_btn.setChecked(True)
            else:
                self.lights_btn.setStyleSheet("")  # Original theme
                self.lights_btn.setChecked(False)

        # Driver state (update only if visible)
        if self.driver_state_group.isVisible():
            self.driver_state_label.setText(f"State: {driver_state.state_classification.upper()}")
            self.drowsiness_bar.setValue(int(driver_state.drowsiness_level * 100))
            self.ear_label.setText(f"Eye Aspect Ratio: {driver_state.eye_aspect_ratio:.3f}")
            self.blink_label.setText(f"Blink Rate: {driver_state.blink_rate:.0f}/min")
            self.emotion_label.setText(f"Emotion: {driver_state.emotion.capitalize()}")

        # Behavior state
        if self.behavior_group.isVisible():
            self.behavior_label.setText(f"Behavior: {behavior_state.behavior_classification.upper()}")
            self.risk_bar.setValue(int(behavior_state.risk_index * 100))
            self.aggression_bar.setValue(int(behavior_state.aggression_score * 100))
            self.stability_bar.setValue(int(behavior_state.stability_score * 100))
            self.events_label.setText(
                f"Rapid Accel: {behavior_state.rapid_acceleration_count} | Hard Braking: {behavior_state.hard_braking_count}"
            )

        # Alerts
        self.overspeed_warning.setVisible(vehicle_state.overspeed)
        self.overheat_warning.setVisible(vehicle_state.overheating)
        self.drowsy_warning.setVisible(driver_state.state_classification in ["drowsy", "fatigued"])

    # -----------------------------
    # Adaptive methods
    # -----------------------------
    @pyqtSlot(object)
    def adapt_interface(self, adaptation):
        """Adapt the interface based on decision engine output"""
        logger.info(f"Adapting interface: {adaptation.reason}")

        self._apply_theme(adaptation.color_theme)
        self._apply_complexity(adaptation.complexity)
        self._apply_brightness(adaptation.brightness)
        self.adaptation_label.setText(adaptation.reason)

        self.current_theme = adaptation.color_theme
        self.current_complexity = adaptation.complexity

    def _apply_theme(self, theme: ColorTheme):
        colors = self.THEMES[theme]

        stylesheet = f"""
            QMainWindow, QWidget {{
                background-color: {colors['bg']};
                color: {colors['fg']};
            }}
            QGroupBox {{
                border: 2px solid {colors['accent']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: {colors['fg']};
                /* Maintain consistent size regardless of theme */
                min-height: 120px;
            }}
            QGroupBox::title {{
                color: {colors['accent']};
                font-weight: bold;
                font-size: 12px;
            }}
            QProgressBar {{
                border: 2px solid {colors['accent']};
                border-radius: 5px;
                text-align: center;
                /* Keep consistent dimensions */
                height: 16px;
                min-height: 16px;
                max-height: 16px;
            }}
            QProgressBar::chunk {{
                background-color: {colors['accent']};
            }}
            QPushButton {{
                background-color: {colors['accent']};
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                /* Maintain consistent button size */
                min-width: 80px;
                min-height: 40px;
            }}
            QPushButton:hover {{
                background-color: {colors['warning']};
            }}
            QPushButton:pressed {{
                background-color: {colors['danger']};
            }}
            QLabel {{
                color: {colors['fg']};
                /* Consistent font sizes */
                font-size: 11px;
            }}
        """
        self.setStyleSheet(stylesheet)

    def _apply_complexity(self, complexity: UIComplexity):
        # Use setVisible for better layout consistency
        if complexity == UIComplexity.MINIMAL:
            self.behavior_group.setVisible(False)
            self.driver_state_group.setVisible(False)
        elif complexity == UIComplexity.REDUCED:
            self.driver_state_group.setVisible(True)
            self.behavior_group.setVisible(False)
        else:
            self.driver_state_group.setVisible(True)
            self.behavior_group.setVisible(True)

    def _apply_brightness(self, brightness: float):
        self.setWindowOpacity(brightness)

    # -----------------------------
    # Alerts
    # -----------------------------
    @pyqtSlot(object)
    def show_alert(self, alert):
        self.alert_display.setText(f"{alert.title}\n{alert.message}")
        self.alert_display.show()
        self.alert_display.raise_()

        if alert.duration > 0:
            QTimer.singleShot(alert.duration * 1000, self.alert_display.hide)

    # -----------------------------
    # Auto Drive
    # -----------------------------
    def _toggle_auto_drive(self):
        if not hasattr(self, 'auto_drive_timer'):
            self.auto_drive_timer = QTimer()
            self.auto_drive_timer.timeout.connect(self.vehicle_simulator.simulate_random_driving)

        if self.auto_drive_timer.isActive():
            self.auto_drive_timer.stop()
        else:
            self.auto_drive_timer.start(1000)