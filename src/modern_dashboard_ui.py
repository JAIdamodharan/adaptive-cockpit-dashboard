"""Modern Adaptive Dashboard UI Module
Enhanced PyQt5-based dashboard with improved aesthetics and adaptive interface
"""

import math
import logging
import threading
import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QProgressBar, QFrame, QGroupBox, 
    QSplitter, QScrollArea, QStatusBar, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QPropertyAnimation, QEasingCurve, QRect, QRectF, QPointF
from PyQt5.QtGui import QImage, QFont, QColor, QLinearGradient, QRadialGradient, QPainter, QBrush, QPixmap, QPen
try:
    import sounddevice as sd
    _AUDIO_AVAILABLE = True
except Exception:
    _AUDIO_AVAILABLE = False

from decision_engine import UIComplexity, ColorTheme

logger = logging.getLogger(__name__)


class ModernProgressBar(QProgressBar):
    """Rounded progress bar whose colour reflects severity.

    mode="high_bad": fills green -> amber -> red as the value rises (temperature, drowsiness).
    mode="low_bad":  red when nearly empty, green when full (fuel).
    """
    def __init__(self, mode="high_bad"):
        super().__init__()
        self._text_visible = False
        self._mode = mode
        self.setTextVisible(False)

    def textVisible(self):
        return self._text_visible

    def setTextVisible(self, visible):
        super().setTextVisible(visible)
        self._text_visible = visible

    def _level_color(self, frac):
        severity = frac if self._mode == "high_bad" else 1.0 - frac
        if severity < 0.6:
            return QColor(46, 204, 113)
        if severity < 0.85:
            return QColor(241, 196, 15)
        return QColor(231, 76, 60)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 90))
        painter.drawRoundedRect(rect, radius, radius)

        span = max(self.maximum() - self.minimum(), 1)
        frac = min(max((self.value() - self.minimum()) / span, 0.0), 1.0)
        if frac > 0:
            fill = QRectF(rect.x(), rect.y(), max(rect.width() * frac, rect.height()), rect.height())
            base = self._level_color(frac)
            grad = QLinearGradient(fill.topLeft(), fill.topRight())
            grad.setColorAt(0, base.darker(130))
            grad.setColorAt(1, base.lighter(115))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(fill, radius, radius)

        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        if self.textVisible():
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Helvetica Neue", 9, QFont.Bold))
            painter.drawText(self.rect(), Qt.AlignCenter, f"{self.value()}%")


class ModernGauge(QWidget):
    """Circular gauge with tick marks, colour zones, glowing arc and a needle."""
    START_ANGLE = 225   # degrees, measured counter-clockwise from 3 o'clock
    SWEEP = 270

    def __init__(self, title="", unit="", max_value=100, redline=0.85):
        super().__init__()
        self.title = title
        self.unit = unit
        self.max_value = max_value
        self.redline = redline
        self.value = 0
        self._shown = 0.0
        self.setMinimumSize(170, 170)
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._step)

    def set_value(self, value):
        self.value = max(0, min(value, self.max_value))
        if not self._anim.isActive():
            self._anim.start(16)

    def _step(self):
        diff = self.value - self._shown
        if abs(diff) < self.max_value * 0.002:
            self._shown = self.value
            self._anim.stop()
        else:
            self._shown += diff * 0.2
        self.update()

    def _zone_color(self, frac):
        if frac < 0.6:
            return QColor(46, 204, 113)
        if frac < self.redline:
            return QColor(241, 196, 15)
        return QColor(231, 76, 60)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        side = min(w, h)
        painter.translate(w / 2, h / 2)
        r = side / 2 - 14
        frac = self._shown / self.max_value if self.max_value else 0

        # Dial face
        face = QRadialGradient(0, 0, r + 8)
        face.setColorAt(0, QColor(40, 44, 56))
        face.setColorAt(1, QColor(14, 16, 22))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(face))
        painter.drawEllipse(QPointF(0, 0), r + 8, r + 8)

        arc_rect = QRectF(-r, -r, 2 * r, 2 * r)
        pen_w = max(8, r * 0.09)

        # Track
        painter.setBrush(Qt.NoBrush)
        track = QPen(QColor(255, 255, 255, 25), pen_w)
        track.setCapStyle(Qt.RoundCap)
        painter.setPen(track)
        painter.drawArc(arc_rect, self.START_ANGLE * 16, -self.SWEEP * 16)

        # Value arc (glow + solid)
        color = self._zone_color(frac)
        span = int(-self.SWEEP * frac * 16)
        if span:
            glow = QColor(color)
            glow.setAlpha(60)
            gp = QPen(glow, pen_w + 8)
            gp.setCapStyle(Qt.RoundCap)
            painter.setPen(gp)
            painter.drawArc(arc_rect, self.START_ANGLE * 16, span)
            vp = QPen(color, pen_w)
            vp.setCapStyle(Qt.RoundCap)
            painter.setPen(vp)
            painter.drawArc(arc_rect, self.START_ANGLE * 16, span)

        # Ticks
        major = 10
        for i in range(major * 2 + 1):
            t = i / (major * 2)
            ang = math.radians(self.START_ANGLE - self.SWEEP * t)
            is_major = i % 2 == 0
            r_out = r - pen_w - 4
            r_in = r_out - (10 if is_major else 5)
            tick_color = QColor(231, 76, 60, 200) if t >= self.redline else QColor(255, 255, 255, 150 if is_major else 70)
            painter.setPen(QPen(tick_color, 2 if is_major else 1))
            painter.drawLine(QPointF(r_out * math.cos(ang), -r_out * math.sin(ang)),
                             QPointF(r_in * math.cos(ang), -r_in * math.sin(ang)))

        # Needle
        ang = math.radians(self.START_ANGLE - self.SWEEP * frac)
        needle_len = r * 0.72
        painter.setPen(QPen(QColor(255, 255, 255, 230), 2.5, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(0, 0), QPointF(needle_len * math.cos(ang), -needle_len * math.sin(ang)))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(0, 0), 6, 6)

        # Readout
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Helvetica Neue", max(13, int(r * 0.26)), QFont.Bold))
        value_txt = f"{self._shown:.1f}" if self.max_value <= 20 else f"{int(round(self._shown))}"
        painter.drawText(QRectF(-r, r * 0.38, 2 * r, r * 0.35), Qt.AlignCenter, value_txt)
        painter.setPen(QColor(255, 255, 255, 140))
        painter.setFont(QFont("Helvetica Neue", max(8, int(r * 0.10))))
        painter.drawText(QRectF(-r, r * 0.70, 2 * r, r * 0.22), Qt.AlignCenter, self.unit)
        painter.setFont(QFont("Helvetica Neue", max(8, int(r * 0.11)), QFont.Bold))
        painter.drawText(QRectF(-r, r * 0.02 + r * 0.12, 2 * r, r * 0.25), Qt.AlignCenter, self.title)


class AdaptiveDashboardUI(QMainWindow):
    """
    Modern dashboard window with enhanced adaptive interface capabilities
    """

    # Modern color scheme definitions - with consistent sizing and layout
    THEMES = {
        ColorTheme.STANDARD: {
            'bg': '#0d1117', 'fg': '#e6edf3', 'accent': '#2ecc71', 'warning': '#f1c40f',
            'danger': '#e74c3c', 'panel_bg': '#161b22', 'border': '#30363d'
        },
        ColorTheme.CALM: {
            'bg': '#0b1630', 'fg': '#d6e6ff', 'accent': '#5aa9ff', 'warning': '#7fdbda',
            'danger': '#b39ddb', 'panel_bg': '#12214a', 'border': '#27407a'
        },
        ColorTheme.ALERT: {
            'bg': '#1f1a05', 'fg': '#fff8e1', 'accent': '#ffca28', 'warning': '#ffa726',
            'danger': '#ff7043', 'panel_bg': '#2b2408', 'border': '#6b5a10'
        },
        ColorTheme.DANGER: {
            'bg': '#2a0a0c', 'fg': '#ffecec', 'accent': '#ff5252', 'warning': '#ff9100',
            'danger': '#ff1744', 'panel_bg': '#3b1014', 'border': '#8e1b24'
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

        # Animation for transitions
        self.animation = None

        logger.info("Modern Dashboard UI initialized")

    def _init_ui(self):
        """Initialize the modern user interface"""
        self.setWindowTitle("AI-Powered Adaptive Vehicle Dashboard")
        # Fit the window to the screen instead of forcing a fixed large size
        from PyQt5.QtWidgets import QApplication
        avail = QApplication.primaryScreen().availableGeometry()
        width = min(1500, int(avail.width() * 0.92))
        height = min(1040, int(avail.height() * 0.92))
        self.resize(width, height)
        self.move(avail.x() + (avail.width() - width) // 2, avail.y() + (avail.height() - height) // 2)
        self.setMinimumSize(1000, 700)

        # Central widget
        central_widget = QWidget()
        central_widget.setObjectName("central")
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header_layout = QHBoxLayout()
        
        # Removed car emoji for more professional look - added spacer to center the title
        header_layout.addStretch()  # Add stretch to push content to center
        
        self.header_label = QLabel("ADAPTIVE COCKPIT")
        self.header_label.setFont(QFont("Helvetica Neue", 22, QFont.Bold))
        self.header_label.setStyleSheet("letter-spacing: 6px;")
        header_layout.addWidget(self.header_label)
        
        header_layout.addStretch()  # Add stretch on the other side to center the title
        
        # Status label on the right
        self.status_label = QLabel("LIVE")
        self.status_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.status_label.setStyleSheet("color: #2ecc71; font-weight: bold; padding: 4px 12px; border: 1px solid #2ecc71; border-radius: 12px;")
        header_layout.addWidget(self.status_label)
        
        main_layout.addLayout(header_layout)

        # Content area
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(5)
        content_splitter.setChildrenCollapsible(False)  # Prevent panels from collapsing
        content_splitter.setOpaqueResize(True)  # For consistent resizing
        
        # Left side: Vehicle instruments
        self.instruments_panel = self._create_instruments_panel()
        self.driver_panel = self._create_driver_state_panel()
        
        # Left: instruments; centre: behaviour + driver monitoring stacked
        content_splitter.addWidget(self.instruments_panel)

        self.behavior_panel = self._create_behavior_panel()
        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.setHandleWidth(5)
        left_splitter.setChildrenCollapsible(False)
        left_splitter.addWidget(self.behavior_panel)
        left_splitter.addWidget(self.driver_panel)
        left_splitter.setSizes([200, 420])
        content_splitter.addWidget(left_splitter)

        # Right: Alerts panel
        self.alerts_panel = self._create_alerts_panel()
        content_splitter.addWidget(self.alerts_panel)
        
        # Set consistent proportional sizes for splitter
        content_splitter.setSizes([520, 480, 400])
        
        # Store splitter references for maintaining consistent sizes
        self.content_splitter = content_splitter
        self.left_splitter = left_splitter
        main_layout.addWidget(content_splitter)

        # Bottom: Control panel
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)

        # Floating alert display
        self.alert_display = QLabel("")
        self.alert_display.setFont(QFont("Arial", 16, QFont.Bold))
        self.alert_display.setAlignment(Qt.AlignCenter)
        self.alert_display.setWordWrap(True)
        self.alert_display.setStyleSheet("""
            QLabel {
                background-color: rgba(244, 67, 54, 220);
                color: white;
                padding: 20px;
                border-radius: 15px;
                min-height: 80px;
            }
        """)
        self.alert_display.setParent(self)
        self.alert_display.setGeometry(300, 50, 900, 100)
        self.alert_display.hide()

        # Status bar
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("Ready - Monitoring Driver and Vehicle Status")

        # Apply initial theme
        self._apply_theme(self.current_theme)

    # -----------------------------
    # Panel creation methods
    # -----------------------------
    def _create_instruments_panel(self) -> QGroupBox:
        group = QGroupBox("VEHICLE INSTRUMENTS")
        group.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 30, 15, 15)
        
        # Allow the instruments panel to grow as needed so nothing is clipped
        group.setMinimumSize(420, 430)
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Speedometer
        speed_layout = QHBoxLayout()
        self.speed_gauge = ModernGauge(title="SPEED", unit="km/h", max_value=200)
        self.speed_gauge.setMinimumSize(150, 150)
        self.speed_gauge.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        speed_layout.addWidget(self.speed_gauge)
        
        self.rpm_gauge = ModernGauge(title="RPM", unit="x1000 rpm", max_value=8, redline=0.8)
        self.rpm_gauge.setMinimumSize(150, 150)
        self.rpm_gauge.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        speed_layout.addWidget(self.rpm_gauge)
        layout.addLayout(speed_layout)

        # Horizontal progress bars
        bottom_layout = QGridLayout()
        
        # Fuel level
        bottom_layout.addWidget(QLabel("FUEL:"), 0, 0)
        self.fuel_bar = ModernProgressBar(mode="low_bad")
        self.fuel_bar.setMinimumHeight(16)
        bottom_layout.addWidget(self.fuel_bar, 0, 1)

        # Engine temperature
        bottom_layout.addWidget(QLabel("TEMP:"), 1, 0)
        self.temp_bar = ModernProgressBar()
        self.temp_bar.setMinimumHeight(16)
        bottom_layout.addWidget(self.temp_bar, 1, 1)
        
        # Odometer
        self.odometer_label = QLabel("ODO: 0.0 km")
        self.odometer_label.setFont(QFont("Arial", 14))
        self.odometer_label.setMinimumHeight(20)
        bottom_layout.addWidget(self.odometer_label, 2, 0, 1, 2)

        # Gear indicator
        gear_row = QHBoxLayout()
        gear_title = QLabel("GEAR:")
        gear_title.setFont(QFont("Arial", 14, QFont.Bold))
        gear_row.addWidget(gear_title)
        self.gear_label = QLabel("P")
        self.gear_label.setFont(QFont("Arial", 28, QFont.Bold))
        self.gear_label.setAlignment(Qt.AlignCenter)
        self.gear_label.setMinimumSize(60, 50)
        self.gear_label.setStyleSheet(
            "border: 2px solid #555555; border-radius: 8px;"
            "background: #1e1e1e; color: #4CAF50; padding: 4px 12px;"
        )
        gear_row.addWidget(self.gear_label)
        gear_row.addStretch()
        bottom_layout.addLayout(gear_row, 3, 0, 1, 2)

        # Indicators
        indicators_layout = QHBoxLayout()
        self.left_indicator = QLabel("◀")
        self.left_indicator.setFont(QFont("Arial", 20))
        self.left_indicator.setStyleSheet("color: gray;")
        self.left_indicator.setMinimumSize(30, 30)
        indicators_layout.addWidget(self.left_indicator)

        self.headlights_indicator = QLabel("💡")
        self.headlights_indicator.setFont(QFont("Arial", 20))
        self.headlights_indicator.setStyleSheet("color: gray;")
        self.headlights_indicator.setMinimumSize(30, 30)
        indicators_layout.addWidget(self.headlights_indicator)

        self.right_indicator = QLabel("▶")
        self.right_indicator.setFont(QFont("Arial", 20))
        self.right_indicator.setStyleSheet("color: gray;")
        self.right_indicator.setMinimumSize(30, 30)
        indicators_layout.addWidget(self.right_indicator)

        bottom_layout.addLayout(indicators_layout, 4, 0, 1, 2)
        layout.addLayout(bottom_layout)

        return group

    def _create_driver_state_panel(self) -> QGroupBox:
        group = QGroupBox("DRIVER MONITORING")
        group.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 30, 15, 15)
        
        # Set consistent size to maintain layout consistency
        group.setMinimumSize(350, 340)
        group.setMaximumSize(16777215, 460)  # Use max int for unlimited width expansion
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Driver state label
        self.driver_state_label = QLabel("DRIVER: NORMAL")
        self.driver_state_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.driver_state_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.driver_state_label)

        # Drowsiness
        drowsiness_layout = QHBoxLayout()
        drowsiness_layout.addWidget(QLabel("DROWSINESS:"))
        self.drowsiness_bar = ModernProgressBar()
        self.drowsiness_bar.setMaximum(100)
        self.drowsiness_bar.setMinimumHeight(16)
        drowsiness_layout.addWidget(self.drowsiness_bar, 1)
        layout.addLayout(drowsiness_layout)

        # Eye Aspect Ratio
        ear_layout = QHBoxLayout()
        ear_layout.addWidget(QLabel("EAR:"))
        self.ear_label = QLabel("0.30")
        self.ear_label.setMinimumWidth(50)
        ear_layout.addWidget(self.ear_label, 1)
        layout.addLayout(ear_layout)

        # NEW: Mouth Aspect Ratio
        mar_layout = QHBoxLayout()
        mar_layout.addWidget(QLabel("MAR:"))
        self.mar_label = QLabel("0.10")
        self.mar_label.setMinimumWidth(50)
        mar_layout.addWidget(self.mar_label, 1)
        
        # Yawn count
        self.yawn_count_label = QLabel("YAWNS: 0")
        self.yawn_count_label.setFont(QFont("Arial", 10, QFont.Bold))
        mar_layout.addWidget(self.yawn_count_label)
        layout.addLayout(mar_layout)

        # NEW: Head Pose
        pose_layout = QHBoxLayout()
        pose_layout.addWidget(QLabel("POSE:"))
        self.pitch_label = QLabel("P: 0°")
        self.yaw_label = QLabel("Y: 0°")
        self.roll_label = QLabel("R: 0°")
        for lbl in [self.pitch_label, self.yaw_label, self.roll_label]:
            lbl.setMinimumWidth(45)
            pose_layout.addWidget(lbl)
        layout.addLayout(pose_layout)

        # Blink rate
        blink_layout = QHBoxLayout()
        blink_layout.addWidget(QLabel("BLINK RATE:"))
        self.blink_label = QLabel("20/min")
        self.blink_label.setMinimumWidth(50)
        blink_layout.addWidget(self.blink_label, 1)
        layout.addLayout(blink_layout)

        # Emotion
        emotion_layout = QHBoxLayout()
        emotion_layout.addWidget(QLabel("EMOTION:"))
        self.emotion_label = QLabel("Calm")
        self.emotion_label.setMinimumWidth(50)
        emotion_layout.addWidget(self.emotion_label, 1)
        layout.addLayout(emotion_layout)
        
        # Emotion Confidence
        confidence_layout = QHBoxLayout()
        confidence_layout.addWidget(QLabel("CONFIDENCE:"))
        self.emotion_confidence_label = QLabel("85%")
        self.emotion_confidence_label.setMinimumWidth(50)
        confidence_layout.addWidget(self.emotion_confidence_label, 1)
        layout.addLayout(confidence_layout)

        # Alert icon
        self.alert_icon_label = QLabel("")
        self.alert_icon_label.setAlignment(Qt.AlignCenter)
        self.alert_icon_label.setFont(QFont("Arial", 32))
        layout.addWidget(self.alert_icon_label)

        return group

    def _create_behavior_panel(self) -> QGroupBox:
        group = QGroupBox("DRIVING BEHAVIOR")
        group.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 30, 15, 15)
        
        # Set consistent size to maintain layout consistency
        group.setMinimumSize(350, 340)
        group.setMaximumSize(16777215, 460)  # Use max int for unlimited width expansion
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.behavior_label = QLabel("BEHAVIOR: SAFE")
        self.behavior_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.behavior_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.behavior_label)

        # Behavior metrics
        metrics_layout = QGridLayout()
        
        # Risk
        metrics_layout.addWidget(QLabel("RISK:"), 0, 0)
        self.risk_bar = ModernProgressBar()
        self.risk_bar.setMaximum(100)
        self.risk_bar.setMinimumHeight(16)
        metrics_layout.addWidget(self.risk_bar, 0, 1)

        # Aggregation
        metrics_layout.addWidget(QLabel("AGGR:"), 1, 0)
        self.aggression_bar = ModernProgressBar()
        self.aggression_bar.setMaximum(100)
        self.aggression_bar.setMinimumHeight(16)
        metrics_layout.addWidget(self.aggression_bar, 1, 1)

        # Stability
        metrics_layout.addWidget(QLabel("STBL:"), 2, 0)
        self.stability_bar = ModernProgressBar(mode="low_bad")
        self.stability_bar.setMaximum(100)
        self.stability_bar.setMinimumHeight(16)
        metrics_layout.addWidget(self.stability_bar, 2, 1)

        layout.addLayout(metrics_layout)

        # Event counts
        self.events_label = QLabel("Events: Accel: 0 | Brake: 0")
        self.events_label.setFont(QFont("Arial", 12))
        self.events_label.setMinimumHeight(20)
        layout.addWidget(self.events_label)

        # Behavior chart
        self.behavior_chart = QLabel("Behavior Trend: ▸▸▸")
        self.behavior_chart.setFont(QFont("Arial", 10))
        self.behavior_chart.setAlignment(Qt.AlignCenter)
        self.behavior_chart.setMinimumHeight(20)
        layout.addWidget(self.behavior_chart)

        layout.addStretch()
        return group

    def _create_alerts_panel(self) -> QGroupBox:
        group = QGroupBox("ALERTS & INSIGHTS")
        group.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 30, 15, 15)

        # Live driver camera preview
        self.camera_label = QLabel("CAMERA OFF\nNo video from the driver monitor")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumHeight(230)
        self.camera_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.camera_label.setStyleSheet(
            "background: #05070a; color: #8b949e; border: 1px solid #30363d; border-radius: 10px;")
        layout.addWidget(self.camera_label)
        self.camera_timer = QTimer(self)
        self.camera_timer.timeout.connect(self._update_camera_preview)
        self.camera_timer.start(66)  # ~15 FPS

        # Active alerts scroll area
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.alerts_layout = QVBoxLayout(scroll_widget)
        self.alerts_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(200)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.viewport().setStyleSheet("background: transparent;")
        scroll_widget.setStyleSheet("background: transparent;")
        layout.addWidget(scroll_area)

        # Warning icons
        warnings_layout = QGridLayout()
        self.overspeed_warning = QLabel("🚨")
        self.overheat_warning = QLabel("🔥")
        self.drowsy_warning = QLabel("😴")
        
        for i, w in enumerate([self.overspeed_warning, self.overheat_warning, self.drowsy_warning]):
            w.setFont(QFont("Arial", 24))
            w.setAlignment(Qt.AlignCenter)
            w.hide()
        
        warnings_layout.addWidget(QLabel("SPEED:"), 0, 0)
        warnings_layout.addWidget(self.overspeed_warning, 0, 1)
        warnings_layout.addWidget(QLabel("ENGINE:"), 1, 0)
        warnings_layout.addWidget(self.overheat_warning, 1, 1)
        warnings_layout.addWidget(QLabel("DRIVER:"), 2, 0)
        warnings_layout.addWidget(self.drowsy_warning, 2, 1)
        layout.addLayout(warnings_layout)

        # Current adaptation
        layout.addWidget(QLabel("CURRENT MODE:"))
        self.adaptation_label = QLabel("Normal operation")
        self.adaptation_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.adaptation_label.setWordWrap(True)
        layout.addWidget(self.adaptation_label)

        # System status
        self.system_status_label = QLabel("Status: Healthy")
        self.system_status_label.setFont(QFont("Arial", 10))
        layout.addWidget(self.system_status_label)

        layout.addStretch()
        return group

    def _create_control_panel(self) -> QFrame:
        frame = QFrame()
        frame.setFrameStyle(QFrame.NoFrame)
        layout = QHBoxLayout(frame)
        layout.setSpacing(10)
        
        # Set minimum size to maintain layout consistency
        frame.setMinimumHeight(80)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Accelerator
        self.accel_btn = QPushButton("⬆ ACCELERATE")
        self.accel_btn.setMinimumSize(100, 50)
        self.accel_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Store original color to restore it later
        original_style = self.accel_btn.styleSheet()
        
        def on_accel_press():
            # Disengage park before accelerating
            if self.vehicle_simulator.parked:
                self.vehicle_simulator.disengage_park()
                self._update_park_btn_style()
            self.vehicle_simulator.set_accelerator(0.8)
            self.accel_btn.setStyleSheet("background-color: #FF5722; color: white;")

        def on_accel_release():
            self.vehicle_simulator.set_accelerator(0.0)
            self.accel_btn.setStyleSheet(original_style)

        self.accel_btn.pressed.connect(on_accel_press)
        self.accel_btn.released.connect(on_accel_release)
        layout.addWidget(self.accel_btn)

        # Brake
        self.brake_btn = QPushButton("⬇ BRAKE")
        self.brake_btn.setMinimumSize(100, 50)
        self.brake_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        def on_brake_press():
            self.vehicle_simulator.set_brake(0.8)
            # Visual feedback
            self.brake_btn.setStyleSheet("background-color: #D32F2F; color: white;")  # Dark red when pressed
        
        def on_brake_release():
            self.vehicle_simulator.set_brake(0.0)
            # Restore original color
            self.brake_btn.setStyleSheet(original_style)
        
        self.brake_btn.pressed.connect(on_brake_press)
        self.brake_btn.released.connect(on_brake_release)
        layout.addWidget(self.brake_btn)

        # Left indicator - with toggle visual feedback
        self.left_ind_btn = QPushButton("◀")
        self.left_ind_btn.setMinimumSize(60, 50)
        self.left_ind_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.left_ind_btn.setCheckable(True)  # Make it toggle-able
        initial_left_state = self.vehicle_simulator.get_current_state().left_indicator
        
        def toggle_left_indicator():
            self.vehicle_simulator.toggle_left_indicator()
            # Visual feedback - toggle button appearance based on state
            current_state = self.vehicle_simulator.get_current_state()
            if current_state.left_indicator:
                self.left_ind_btn.setStyleSheet("background-color: #4CAF50; color: white;")
            else:
                self.left_ind_btn.setStyleSheet(original_style)
        
        self.left_ind_btn.clicked.connect(toggle_left_indicator)
        layout.addWidget(self.left_ind_btn)

        # Right indicator - with toggle visual feedback  
        self.right_ind_btn = QPushButton("▶")
        self.right_ind_btn.setMinimumSize(60, 50)
        self.right_ind_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.right_ind_btn.setCheckable(True)  # Make it toggle-able
        
        def toggle_right_indicator():
            self.vehicle_simulator.toggle_right_indicator()
            # Visual feedback - toggle button appearance based on state
            current_state = self.vehicle_simulator.get_current_state()
            if current_state.right_indicator:
                self.right_ind_btn.setStyleSheet("background-color: #4CAF50; color: white;")
            else:
                self.right_ind_btn.setStyleSheet(original_style)
                
        self.right_ind_btn.clicked.connect(toggle_right_indicator)
        layout.addWidget(self.right_ind_btn)

        # Headlights - with toggle visual feedback
        self.lights_btn = QPushButton("💡")
        self.lights_btn.setMinimumSize(60, 50)
        self.lights_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.lights_btn.setCheckable(True)  # Make it toggle-able
        
        def toggle_headlights():
            self.vehicle_simulator.toggle_headlights()
            # Visual feedback - toggle button appearance based on state
            current_state = self.vehicle_simulator.get_current_state()
            if current_state.headlights:
                self.lights_btn.setStyleSheet("background-color: #FFEB3B; color: black;")
            else:
                self.lights_btn.setStyleSheet(original_style)
                
        self.lights_btn.clicked.connect(toggle_headlights)
        layout.addWidget(self.lights_btn)

        # Park (P) gear button – toggles park on/off
        self.park_btn = QPushButton("🅿 PARK")
        self.park_btn.setMinimumSize(100, 50)
        self.park_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.park_btn.setCheckable(True)
        self.park_btn.setChecked(True)  # starts in PARK
        self._update_park_btn_style()   # set initial appearance

        def toggle_park():
            if self.vehicle_simulator.parked:
                self.vehicle_simulator.disengage_park()
            else:
                self.vehicle_simulator.engage_park()
            self._update_park_btn_style()

        self.park_btn.clicked.connect(toggle_park)
        layout.addWidget(self.park_btn)

        # Auto Drive
        self.random_btn = QPushButton("AUTO DRIVE")
        self.random_btn.setMinimumSize(100, 50)
        self.random_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.random_btn.clicked.connect(self._toggle_auto_drive)
        layout.addWidget(self.random_btn)

        return frame

    # -----------------------------
    # Dashboard update methods
    # -----------------------------
    @pyqtSlot()
    def _update_dashboard(self):
        """Update dashboard displays with current data"""
        try:
            vehicle_state = self.vehicle_simulator.get_current_state()
            driver_state = self.driver_monitor.get_current_state()
            behavior_state = self.behavior_analyzer.get_current_metrics()

            # Vehicle instruments
            self.speed_gauge.set_value(vehicle_state.speed)
            self.rpm_gauge.set_value(vehicle_state.rpm / 1000)  # Scale for display
            self.fuel_bar.setValue(int(vehicle_state.fuel_level))
            self.temp_bar.setValue(int(vehicle_state.engine_temp))
            self.odometer_label.setText(f"ODO: {vehicle_state.odometer:.2f} km")

            # Gear indicator
            gear = vehicle_state.gear
            self.gear_label.setText(gear)
            if gear in ('P', 'N'):
                gear_color = '#888888'
            elif gear in ('1', '2', '3'):
                gear_color = '#4CAF50'   # green - lower gears
            else:
                gear_color = '#5390d9'   # blue - higher gears
            self.gear_label.setStyleSheet(
                f"border: 2px solid {gear_color}; border-radius: 8px;"
                f"background: #1e1e1e; color: {gear_color}; padding: 4px 12px;"
            )


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

            # Driver state
            state_text = driver_state.state_classification.upper()
            if not getattr(driver_state, 'calibrated', True):
                pct = int(getattr(driver_state, 'calibration_progress', 0.0) * 100)
                self.driver_state_label.setText(f"CALIBRATING... {pct}%  (look at the road)")
            else:
                self.driver_state_label.setText(f"DRIVER: {state_text}")
            
            # Update driver state styling based on state
            if state_text == "NORMAL":
                self.driver_state_label.setStyleSheet("color: #4CAF50;")
                self.alert_icon_label.setText("")
            elif state_text == "FATIGUED":
                self.driver_state_label.setStyleSheet("color: #FFC107;")
                self.alert_icon_label.setText("⚠️")
            elif state_text == "DROWSY":
                self.driver_state_label.setStyleSheet("color: #f44336;")
                self.alert_icon_label.setText("😴")
            else:
                self.driver_state_label.setStyleSheet("color: #5390d9;")
                self.alert_icon_label.setText("")
            
            self.drowsiness_bar.setValue(int(driver_state.drowsiness_level * 100))
            self.ear_label.setText(f"{driver_state.eye_aspect_ratio:.3f}")
            self.mar_label.setText(f"{driver_state.mouth_aspect_ratio:.3f}")
            self.yawn_count_label.setText(f"YAWNS: {driver_state.yawn_count}")
            
            # Head pose with color coding for warnings
            self.pitch_label.setText(f"P: {driver_state.head_pitch:.0f}°")
            self.yaw_label.setText(f"Y: {driver_state.head_yaw:.0f}°")
            self.roll_label.setText(f"R: {driver_state.head_roll:.0f}°")
            
            # Visual feedback for head pose
            if abs(driver_state.head_pitch) > 15:
                self.pitch_label.setStyleSheet("color: #FFC107;")
            else:
                self.pitch_label.setStyleSheet("")
                
            if abs(driver_state.head_yaw) > 25:
                self.yaw_label.setStyleSheet("color: #FFC107;")
            else:
                self.yaw_label.setStyleSheet("")

            self.blink_label.setText(f"{driver_state.blink_rate:.0f}/min")
            self.emotion_label.setText(driver_state.emotion.capitalize())
            self.emotion_confidence_label.setText(f"{int(driver_state.emotion_confidence * 100)}%")

            # Behavior state
            behavior_text = behavior_state.behavior_classification.upper()
            if behavior_text == "SAFE":
                self.behavior_label.setStyleSheet("color: #4CAF50;")
            elif behavior_text == "MODERATE":
                self.behavior_label.setStyleSheet("color: #5390d9;")
            elif behavior_text == "AGGRESSIVE":
                self.behavior_label.setStyleSheet("color: #FFC107;")
            elif behavior_text == "RISKY":
                self.behavior_label.setStyleSheet("color: #f44336;")
            else:
                self.behavior_label.setStyleSheet("color: #ffffff;")
            
            self.behavior_label.setText(f"BEHAVIOR: {behavior_text}")
            self.risk_bar.setValue(int(behavior_state.risk_index * 100))
            self.aggression_bar.setValue(int(behavior_state.aggression_score * 100))
            self.stability_bar.setValue(int(behavior_state.stability_score * 100))
            self.events_label.setText(
                f"Events: Accel: {behavior_state.rapid_acceleration_count} | Brake: {behavior_state.hard_braking_count}"
            )

            # Alerts
            self.overspeed_warning.setVisible(vehicle_state.overspeed)
            self.overheat_warning.setVisible(vehicle_state.overheating)
            self.drowsy_warning.setVisible(driver_state.state_classification in ["drowsy", "fatigued"])

            # Update status
            status_bar = self.statusBar()
            if status_bar:
                status_bar.showMessage(f"Speed: {vehicle_state.speed:.0f}km/h | Risk: {behavior_state.risk_index*100:.0f}% | Driver: {state_text}")
        except Exception as e:
            logger.error(f"Error updating dashboard: {e}")

    # -----------------------------
    # Adaptive methods
    # -----------------------------
    def _update_camera_preview(self):
        frame = getattr(self.driver_monitor, 'latest_frame', None)
        if frame is None:
            return
        try:
            h, w = frame.shape[:2]
            img = QImage(frame.data, w, h, 3 * w, QImage.Format_BGR888).copy()
            pix = QPixmap.fromImage(img).scaled(
                self.camera_label.width() - 4, self.camera_label.height() - 4,
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.camera_label.setPixmap(pix)
        except Exception as e:
            logger.debug(f"Camera preview update failed: {e}")

    @pyqtSlot(object)
    def adapt_interface(self, adaptation):
        """Adapt the interface based on decision engine output"""
        logger.info(f"Adapting interface: {adaptation.reason}")

        self._apply_theme(adaptation.color_theme)
        self._apply_complexity(adaptation.complexity)

        # Add subtle animation for theme changes
        self._animate_transition()

        self.adaptation_label.setText(adaptation.reason)

        self.current_theme = adaptation.color_theme
        self.current_complexity = adaptation.complexity

        # --- Play alarm every time drowsiness / fatigue is detected ---
        reason_upper = adaptation.reason.upper()
        is_drowsy   = 'DROWSY' in reason_upper or 'DROWSINESS' in reason_upper
        is_critical = 'CRITICAL' in reason_upper
        is_fatigued = 'FATIGUE' in reason_upper

        if is_drowsy or is_critical:
            self._play_drowsy_alarm(priority=1)   # CRITICAL — 3 beeps at 880 Hz
        elif is_fatigued:
            self._play_drowsy_alarm(priority=2)   # WARNING  — 2 beeps at 660 Hz


    def _animate_transition(self):
        """Add subtle transition animation"""
        # Add a subtle pulsing effect to indicate adaptation
        if self.animation:
            self.animation.stop()
        
        self.setWindowOpacity(0.95)
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)
        self.animation.setStartValue(0.95)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()

    def _apply_theme(self, theme: ColorTheme):
        colors = self.THEMES[theme]

        stylesheet = f"""
            QMainWindow, QWidget#central {{ background-color: {colors['bg']}; }}
            QWidget {{ font-family: "Helvetica Neue", "Segoe UI", Arial, sans-serif; }}
            QGroupBox {{
                background-color: {colors['panel_bg']};
                border: 1px solid {colors['border']};
                border-radius: 14px;
                margin-top: 18px;
                padding: 14px;
                color: {colors['fg']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 16px;
                padding: 2px 10px;
                color: {colors['accent']};
                background-color: {colors['bg']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                letter-spacing: 2px;
            }}
            QProgressBar {{ border: none; background: transparent; min-height: 14px; max-height: 14px; }}
            QPushButton {{
                background-color: {colors['panel_bg']};
                color: {colors['fg']};
                border: 1px solid {colors['border']};
                padding: 10px 14px;
                border-radius: 10px;
                font-weight: bold;
                font-size: 13px;
                min-width: 80px;
                min-height: 44px;
            }}
            QPushButton:hover {{ border-color: {colors['accent']}; color: {colors['accent']}; }}
            QPushButton:pressed {{ background-color: {colors['accent']}; color: {colors['bg']}; }}
            QLabel {{ color: {colors['fg']}; font-size: 12px; background: transparent; }}
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: {colors['border']}; border-radius: 4px; min-height: 24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QSplitter::handle {{ background-color: transparent; }}
            QStatusBar {{ background: {colors['bg']}; color: {colors['fg']}; }}
        """
        self.setStyleSheet(stylesheet)

    def _apply_complexity(self, complexity: UIComplexity):
        # Keep everything visible to avoid driver distraction from size/layout shifts
        self.driver_panel.setVisible(True)
        self.behavior_panel.setVisible(True)
            
        # Make sure splitters maintain consistent sizing
        # This ensures layout doesn't shift
        if hasattr(self, 'content_splitter') and hasattr(self, 'left_splitter'):
            # Only reapply if window is visible (to prevent initialization issues)
            if self.isVisible():
                try:
                    self.content_splitter.setSizes(self.content_splitter.sizes())  # Reapply sizes
                    self.left_splitter.setSizes(self.left_splitter.sizes())  # Reapply sizes
                except:
                    # Fallback to defaults if sizes aren't available yet
                    self.content_splitter.setSizes([520, 480, 400])
                    self.left_splitter.setSizes([500, 300])

    # -----------------------------
    # Alerts
    # -----------------------------
    @pyqtSlot(object)
    def show_alert(self, alert):
        # Add to alerts panel
        timestamp = QLabel(f"[{alert.priority}] {alert.title}")
        timestamp.setStyleSheet("color: #FFC107; font-weight: bold; font-size: 12px;")
        self.alerts_layout.addWidget(timestamp)

        message = QLabel(alert.message)
        message.setWordWrap(True)
        message.setStyleSheet("font-size: 11px; margin-bottom: 10px;")
        self.alerts_layout.addWidget(message)

        # Auto-scroll to bottom
        scroll_widget = self.alerts_layout.parentWidget()
        scroll_area = scroll_widget.parent()
        if hasattr(scroll_area, 'ensureWidgetVisible'):
            scroll_area.ensureWidgetVisible(message)

        # Show floating alert
        self.alert_display.setText(f"{alert.title}\n{alert.message}")
        self.alert_display.show()
        self.alert_display.raise_()

        if alert.duration > 0:
            QTimer.singleShot(alert.duration * 1000, self.alert_display.hide)

        # Play audio alarm on high-priority alerts
        self._play_alarm(alert.priority)

    def _play_drowsy_alarm(self, priority):
        """Play a drowsy alarm immediately, with a shorter cooldown."""
        now = __import__('time').time()
        if not hasattr(self, '_drowsy_alarm_last_played'):
            self._drowsy_alarm_last_played = 0
            
        # 3 second cooldown for drowsy specifically to ensure it repeats if condition persists
        if now - self._drowsy_alarm_last_played < 3.0:
            return
            
        self._drowsy_alarm_last_played = now
        # Bypass the 10s cooldown for this specific safety-critical alarm
        self._play_alarm(priority, ignore_cooldown=True)

    def _play_alarm(self, priority, ignore_cooldown=False):
        """Play a beep alarm using sounddevice (non-blocking).

        priority: int  1=CRITICAL, 2=WARNING, 3=INFO
        ignore_cooldown: bool - if True, bypasses the 10s repeat check
        """
        if not _AUDIO_AVAILABLE:
            logger.debug("Audio not available, skipping alarm")
            return

        # Normalise to integer severity
        try:
            p = int(priority)
        except (ValueError, TypeError):
            ps = str(priority).upper()
            p = 1 if ps in ('CRITICAL', 'HIGH') else (2 if ps in ('WARNING', 'MEDIUM') else 3)

        # Per-priority cooldown — avoid constant beeping (10 s minimum between same-priority alarms)
        import time as _time
        now = _time.time()
        if not hasattr(self, '_alarm_last_played'):
            self._alarm_last_played = {}
        if not ignore_cooldown and now - self._alarm_last_played.get(p, 0) < 10.0:
            return
        self._alarm_last_played[p] = now

        # Louder, longer tone patterns
        if p == 1:
            freqs = [880, 880, 880]   # three high beeps — CRITICAL
            dur   = 0.45
        elif p == 2:
            freqs = [660, 660]         # two mid beeps — WARNING
            dur   = 0.5
        else:
            freqs = [440]              # one low beep — INFO
            dur   = 0.6

        logger.info(f"Playing alarm: priority={p}, {len(freqs)}x{freqs[0]}Hz, dur={dur}s")

        def _beep():
            sample_rate = 44100
            gap = np.zeros(int(sample_rate * 0.12), dtype=np.float32)  # 120ms gap between beeps
            for freq in freqs:
                t = np.linspace(0, dur, int(sample_rate * dur), False)
                wave = 0.85 * np.sin(2 * np.pi * freq * t).astype(np.float32)
                # Short fade-in / fade-out to avoid clicks
                fade = min(int(sample_rate * 0.015), len(wave) // 4)
                wave[:fade] *= np.linspace(0, 1, fade)
                wave[-fade:] *= np.linspace(1, 0, fade)
                try:
                    sd.play(np.concatenate([wave, gap]), sample_rate)
                    sd.wait()
                except Exception as e:
                    logger.warning(f"Audio alarm failed: {e}")

        threading.Thread(target=_beep, daemon=True).start()


    # -----------------------------
    # Park button style helper
    # -----------------------------
    def _update_park_btn_style(self):
        """Update PARK button appearance to reflect current parked state."""
        if not hasattr(self, 'park_btn'):
            return
        if self.vehicle_simulator.parked:
            self.park_btn.setChecked(True)
            self.park_btn.setStyleSheet(
                "background-color: #7b1fa2; color: white; font-weight: bold;"
                "border-radius: 6px; font-size: 14px;"
                "border: 3px solid #ce93d8;"
            )
        else:
            self.park_btn.setChecked(False)
            self.park_btn.setStyleSheet(
                "background-color: #4a0072; color: #aaaaaa; font-weight: bold;"
                "border-radius: 6px; font-size: 14px;"
                "border: 3px solid #555555;"
            )

    # -----------------------------
    # Auto Drive
    # -----------------------------
    def _toggle_auto_drive(self):
        if not hasattr(self, 'auto_drive_timer'):
            self.auto_drive_timer = QTimer()
            self.auto_drive_timer.timeout.connect(self.vehicle_simulator.simulate_random_driving)

        if self.auto_drive_timer.isActive():
            self.auto_drive_timer.stop()
            self.random_btn.setText("AUTO DRIVE")
            self.random_btn.setStyleSheet("")
        else:
            # Disengage PARK before starting auto drive
            if self.vehicle_simulator.parked:
                self.vehicle_simulator.disengage_park()
                self._update_park_btn_style()
            self.auto_drive_timer.start(1000)
            self.random_btn.setText("AUTO DRIVE ACTIVE")
            self.random_btn.setStyleSheet("background-color: #FF5722; color: white;")