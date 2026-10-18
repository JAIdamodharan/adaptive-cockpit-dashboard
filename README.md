# Adaptive Cockpit: AI-Powered Adaptive Vehicle Dashboard

An automotive HMI simulator that watches the **driver** (webcam + computer vision) and the **vehicle** (simulated telemetry), then adapts the dashboard in real time: layout complexity, colour theme and prioritised alerts change with driver fatigue, emotion and driving behaviour.

*University project, Automotive Software Engineering.*

![Dashboard](docs/images/dashboard.png)

## Features

- **Driver monitoring**: Eye Aspect Ratio (drowsiness), Mouth Aspect Ratio (yawns), head pose, blink rate and emotion recognition (OpenCV + MediaPipe, optional Keras model).
- **Vehicle simulator**: speed, RPM, gear, fuel, engine temperature, odometer, indicators and headlights.
- **Behaviour analysis**: rolling-window aggression, instability and over-speed scores combined into a risk level.
- **Adaptive decision engine**: rule-based mapping from fused state to UI complexity, colour theme and alerts.
- **Modern PyQt5 UI**: animated dial gauges with colour zones and redline, severity-coloured bars, four themes, floating alerts and audible alarms.

## Architecture

### System overview

```mermaid
flowchart LR
    CAM[/Webcam/] --> DM[Driver Monitor<br/>EAR, MAR, pose, emotion]
    SIM[Vehicle Simulator<br/>speed, rpm, fuel, temp] --> BA[Behavior Analyzer<br/>aggression, stability, risk]
    SIM --> DE
    DM -->|cognitive_state_updated| DE[Adaptive Decision Engine]
    BA -->|behavior_updated| DE
    DE -->|ui_adaptation_required| UI[Dashboard UI<br/>PyQt5]
    DE -->|alert_triggered| UI
    UI -->|accelerate, brake, signals| SIM
    SIM -->|state_updated| BA
```

### Signal flow (one update cycle)

```mermaid
sequenceDiagram
    participant S as VehicleSimulator
    participant D as DriverMonitor
    participant B as BehaviorAnalyzer
    participant E as DecisionEngine
    participant U as DashboardUI
    S->>B: state_updated(vehicle state)
    S->>E: update_vehicle_state
    D->>E: cognitive_state_updated(drowsiness, emotion)
    B->>E: behavior_updated(risk, aggression)
    E->>E: evaluate rules
    E-->>U: ui_adaptation_required(theme, complexity)
    E-->>U: alert_triggered(priority, message)
    U->>U: repaint every 500 ms
```

### Adaptive state machine

```mermaid
stateDiagram-v2
    [*] --> Standard
    Standard --> Calm: stress or aggression detected
    Standard --> Alert: drowsiness rising
    Alert --> Danger: drowsiness critical or high risk
    Calm --> Standard: driver normal
    Alert --> Standard: driver recovered
    Danger --> Alert: risk falling
```

| Theme | UI complexity | Trigger |
|-------|---------------|---------|
| Standard | Full | Normal driving |
| Calm | Reduced | Stress or aggressive driving |
| Alert | Reduced | Early fatigue |
| Danger | Minimal | Critical drowsiness or high risk |

### Module map

```mermaid
classDiagram
    class VehicleSimulator { +start() +stop() +get_current_state() }
    class DriverMonitor { +start() +stop() +find_builtin_camera() +get_current_state() }
    class BehaviorAnalyzer { +process_vehicle_data() +get_current_metrics() }
    class AdaptiveDecisionEngine { +update_vehicle_state() +update_driver_state() +update_behavior_state() }
    class AdaptiveDashboardUI { +adapt_interface() +show_alert() }
    class ModernGauge
    class ModernProgressBar
    AdaptiveDashboardUI o-- ModernGauge
    AdaptiveDashboardUI o-- ModernProgressBar
    AdaptiveDashboardUI --> AdaptiveDecisionEngine
    AdaptiveDecisionEngine --> BehaviorAnalyzer
    AdaptiveDecisionEngine --> DriverMonitor
    AdaptiveDecisionEngine --> VehicleSimulator
```

## Project structure

```
adaptive-dashboard-system/
├── src/
│   ├── main.py                 # entry point, wires modules via Qt signals
│   ├── modern_dashboard_ui.py  # PyQt5 UI (gauges, themes, alerts)
│   ├── dashboard_ui.py         # earlier UI version
│   ├── driver_monitor.py       # computer vision / emotion model
│   ├── vehicle_simulator.py    # telemetry simulation
│   ├── behavior_analyzer.py    # driving behaviour scoring
│   └── decision_engine.py      # adaptation rules
├── config/settings.json        # thresholds and weights
├── tests/                      # pytest suite
├── docs/                       # design documents and images
└── requirements.txt
```

## Getting started

```bash
git clone <this-repo-url>
cd adaptive-dashboard-system
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd src && python main.py
```

On first run macOS asks for camera permission. Without a webcam the vehicle simulation and UI still run.

**Emotion model:** the trained `emotion_model.h5` (about 43 MB) is not stored in git. Place your own model at the project root; the monitor falls back to the geometric features (EAR/MAR/pose) when it is absent.

### Controls

| Control | Action |
|---------|--------|
| Accelerate / Brake | Hold to change speed |
| ◀ ▶ | Toggle turn indicators |
| 💡 | Headlights |
| Park | Shift to park |
| Auto Drive | Random driving for demos |

## Configuration

Tune thresholds in [`config/settings.json`](config/settings.json): EAR drowsiness thresholds, behaviour window and weights, alert durations, UI size.

## Tests

```bash
pytest tests/
```

## Security notes

No credentials or API keys are used. Logs, camera selection state, virtual environments and model weights are excluded through `.gitignore`.

## License

Academic project. Add a license of your choice before reuse.
