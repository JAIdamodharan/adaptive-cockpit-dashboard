# AI-Powered Adaptive Vehicle Dashboard System
## Project Report

**Course:** Automotive Software Engineering  
**Project:** Adaptive Dashboard System  
**Date:** April 2026

---

## 1. Introduction

### 1.1 Background

Road traffic accidents remain one of the leading causes of injury and death worldwide, with driver inattention, fatigue, and drowsiness accounting for a significant proportion of incidents. According to the World Health Organization (WHO), approximately 1.35 million people die each year due to road traffic crashes, many of which are directly attributable to impaired driver awareness. Modern vehicles are increasingly equipped with embedded systems capable of monitoring both the driver and the vehicle in real time; however, most existing dashboard systems present a fixed, static interface regardless of the driver's condition, context, or operational environment.

This project addresses that gap by designing and implementing an **AI-Powered Adaptive Dashboard System** - a real-time vehicle monitoring platform that dynamically reconfigures its colour theme in response to driver state, vehicle health, and driving behaviour, while keeping the UI layout and element sizes constant to minimise spatial disorientation. The system integrates computer-vision-based driver monitoring (eye aspect ratio, mouth aspect ratio, head pose, emotion recognition) with a physics-based vehicle simulator, automatic gear calculation, a rule-based decision engine, and a priority-graded audio alarm system.

### 1.2 Motivation

- Distracted or drowsy driving is responsible for around 25% of all vehicular crashes.
- Static HMIs (Human-Machine Interfaces) do not account for moment-to-moment changes in driver alertness.
- Adaptive colour themes that signal urgency without altering layout reduce cognitive load in critical moments.
- Multi-modal warnings (visual and auditory) provide redundant alert channels that improve response time.

### 1.3 Objectives

1. Design a real-time driver monitoring pipeline using facial landmark detection.
2. Integrate a physics-based vehicle simulator with realistic automatic gear selection (P/N/1-6).
3. Implement a rule-based decision engine mapping driver/vehicle state to colour themes.
4. Ensure UI layout and element sizes are identical across all adaptive modes - only colours change.
5. Add priority-graded audio alarms (sine-wave beeps) for critical, warning, and informational alerts.
6. Provide a dedicated PARK button to safely engage parking gear.
7. Debounce theme changes (5-second minimum) to prevent distracting rapid switching.

### 1.4 Scope

The system is a desktop simulation prototype demonstrating adaptive HMI feasibility. It uses a software-simulated vehicle (not connected to real CAN-bus hardware) and a webcam feed for driver monitoring.

---

## 2. Literature Review

### 2.1 Driver Drowsiness Detection

- **Soukupova and Cech (2016)** introduced the Eye Aspect Ratio (EAR) as a blink-detection metric derived from six facial landmarks per eye. A sustained EAR below 0.25 for more than 48 consecutive frames signals drowsiness.
- **Abtahi et al. (2014)** proposed Mouth Aspect Ratio (MAR) for yawn detection, complementing EAR-based drowsiness systems.
- **Daza et al. (2014)** used head-pose estimation from facial landmarks to detect head nodding associated with microsleep episodes.
- **Viola and Jones (2001)** established Haar cascade face detection, still widely used for real-time embedded performance.
- **MediaPipe FaceMesh (Kartynnik et al., 2019)** provides 468 3D facial landmarks in real time on CPU hardware, enabling EAR, MAR, and head-pose computation without a GPU.

### 2.2 Adaptive Human-Machine Interfaces

- **Regan et al. (2011)** established that secondary task interference is reduced when the HMI adapts to driver workload.
- **Burnett and Donkor (2020)** showed that reducing non-essential UI elements during high-risk scenarios decreases driver reaction time to primary tasks.
- **ISO 15008:2017** defines requirements for visual information in road vehicle displays (luminance contrast, information density).
- The **AIDE project (Engstrom et al., 2005)** demonstrated that context-aware HMIs suppressing non-essential information during critical moments measurably reduce cognitive load.

### 2.3 Vehicle State Monitoring

- **OBD-II** is the standard protocol for accessing real-time vehicle parameters (speed, RPM, coolant temperature, fuel level).
- Gear ratio modelling using speed-band look-up tables is a standard simplification for software simulators without real transmission hardware.

### 2.4 Audio Alarms in Safety-Critical Systems

- **Patterson (1982)** found that sinusoidal warning tones are identifiable within 150 ms, making them superior to speech warnings under stress.
- **ISO 11428 and ISO 11429** specify requirements for auditory danger signals applicable to automotive HMIs.
- Graded alarm systems with distinct frequency profiles reduce alarm fatigue compared to uniform single-tone systems.

---

## 3. Proposed Methodology

### 3.1 System Overview

```
Camera Feed  -->  Driver Monitor  -->  Behaviour Analyzer  -->  Decision Engine  -->  Adaptive UI
Vehicle Sim  -->                                            -->                   -->  Audio Alarms
```

### 3.2 Driver Monitoring Pipeline

1. Frame capture from webcam at ~30 fps.
2. Face detection via MediaPipe FaceMesh (OpenCV Haar Cascade fallback).
3. Landmark extraction: 468 3D facial landmarks.
4. EAR computed per eye, averaged across both.
5. MAR computed from lip landmarks; yawn flagged when MAR > 0.6 sustained > 1 s.
6. Head pose via cv2.solvePnP with canonical 6-point 3D face model.
7. Emotion classified from facial geometry features.
8. State classification: NORMAL / FATIGUED / DROWSY.

### 3.3 Behaviour Analysis

Rolling-window aggregation over vehicle state deltas:
- **Rapid acceleration**: speed delta above threshold per second.
- **Hard braking**: speed delta below negative threshold per second.
- **Aggression score**: weighted event count / window duration.
- **Stability score**: 1 - variance of speed over window.
- **Risk index**: composite of aggression, stability, and drowsiness level.

### 3.4 Decision Engine with Debounce

| Condition | Theme | Debounce |
|---|---|---|
| Normal, low risk | STANDARD (dark grey) | 5 s |
| Fatigued driver | CALM (deep blue) | 5 s |
| Drowsy driver | ALERT (green) | 5 s |
| Drowsy + high risk | DANGER (red) | Immediate |
| Engine overheating | DANGER (red) | Immediate |
| Overspeed | ALERT (green) | 5 s |

Theme changes escalating to DANGER are always applied immediately (safety-first).  
All other theme changes require the new condition to persist for 5 seconds before the UI updates, eliminating rapid flickering.

### 3.5 Gear Calculation

| Gear | Speed Band (km/h) | Gear Ratio |
|---|---|---|
| P/N | 0-1 | - |
| 1 | 1-10 | 3.50 |
| 2 | 10-30 | 2.10 |
| 3 | 30-55 | 1.40 |
| 4 | 55-85 | 1.00 |
| 5 | 85-120 | 0.80 |
| 6 | 120-200 | 0.65 |

RPM = (speed/100) x ratio x 2500, clamped to [800, 8000].  
The PARK button immediately sets gear='P', brake=1.0, and accelerator=0.0.

### 3.6 Audio Alarm System

| Priority | Pattern | Frequency |
|---|---|---|
| CRITICAL / HIGH | 3 rapid beeps | 880 Hz |
| WARNING / MEDIUM | 2 beeps | 660 Hz |
| INFO / LOW | 1 beep | 440 Hz |

Alarms play in daemon threads via sounddevice; the UI remains fully responsive.

---

## 4. System Architecture

### 4.1 Module Structure

```
adaptive-dashboard-system/
  src/
    main.py                  - Entry point; wires all components
    vehicle_simulator.py     - Physics engine + gear calculation
    driver_monitor.py        - MediaPipe facial analysis
    behavior_analyzer.py     - Driving pattern analysis
    decision_engine.py       - Rule engine with 5-second debounce
    modern_dashboard_ui.py   - PyQt5 UI + PARK button + audio alarms
```

### 4.2 Data Flow

```
VehicleSimulator  ->  VehicleState(speed, rpm, gear, fuel, temp, odometer, warnings)
DriverMonitor     ->  DriverState(EAR, MAR, head_pose, emotion, drowsiness, classification)
BehaviorAnalyzer  ->  BehaviorMetrics(risk_index, aggression, stability, events)
DecisionEngine    ->  UIAdaptation(color_theme, reason)  [debounced 5 s]
                      Alert(title, message, priority, duration) [immediate]
AdaptiveDashboardUI
  _apply_theme()       CSS colour swap only - layout never changes
  _update_dashboard()  Live gauge/bar/label/gear updates every 500 ms
  show_alert()         Floating overlay + audio beep (daemon thread)
```

### 4.3 Threading Model

| Thread | Role |
|---|---|
| Qt Main Thread | UI rendering and event loop |
| QTimer 500 ms | Dashboard polling |
| QTimer variable | Vehicle simulation physics tick |
| QTimer variable | Driver monitor frame analysis |
| Python daemon thread | Non-blocking audio alarm playback |

### 4.4 UI Layout

```
+------------------------------------------------------------------+
| Header: AI-POWERED ADAPTIVE DASHBOARD              [LIVE]        |
+--------------------+-----------------+---------------------------+
| VEHICLE INSTRUMENTS| DRIVING BEHAVIOR| ALERTS AND INSIGHTS       |
|  Speed + RPM gauges|  Risk bar       |  Alert scroll area        |
|  Fuel bar          |  Aggression bar |  Warning icons            |
|  Temp bar          |  Stability bar  |  Current mode label       |
|  Odometer          +-----------------+                           |
|  GEAR [  6  ]      | DRIVER MONITORING                          |
|  Left / Light / Rt |  EAR/MAR/Pose                              |
+--------------------+-----------------+---------------------------+
| ACCEL | BRAKE | Left | Right | Lights | PARK | AUTO DRIVE        |
+------------------------------------------------------------------+
```

---

## 5. Algorithm Used

### 5.1 Eye Aspect Ratio (EAR)

Given six eye landmarks P1...P6:
```
EAR = (dist(P2,P6) + dist(P3,P5)) / (2 x dist(P1,P4))
```
Threshold: EAR < 0.25 sustained > 1.5 s --> DROWSY alert.

### 5.2 Mouth Aspect Ratio (MAR)

```
MAR = (dist(A,H) + dist(B,G) + dist(C,F)) / (3 x dist(D,E))
```
Threshold: MAR > 0.60 sustained > 1 s = yawn. Three yawns in 5 min --> DROWSY upgrade.

### 5.3 Head Pose Estimation (solvePnP)

1. Select 6 canonical 3D face model points.
2. Map to 2D landmark positions from FaceMesh.
3. Solve cv2.solvePnP --> rotation vector + translation vector.
4. Convert to Euler angles (pitch, yaw, roll) via Rodrigues decomposition.
5. Thresholds: |yaw| > 25 deg or |pitch| > 15 deg --> inattention flag.

### 5.4 Risk Index

```
risk = 0.4 x aggression + 0.3 x (1 - stability) + 0.3 x drowsiness_level
```

### 5.5 UI Theme Debounce Algorithm

```
On every state update:
  candidate = apply_decision_rules()
  if candidate.theme == current.theme:
      reset pending_candidate
  elif candidate.theme == DANGER and current.theme != DANGER:
      apply immediately           # safety escalation
  else:
      if pending_candidate != candidate:
          pending_candidate = candidate
          pending_since = now
      elif (now - pending_since) >= 5s and (now - last_change) >= 5s:
          apply candidate         # debounce satisfied
```

### 5.6 Vehicle Physics (Euler Integration, dt = 0.5 s)

```
speed -= BRAKE_DECEL x brake x dt           # braking
speed += ACCEL_RATE x accelerator x dt      # acceleration
speed -= NATURAL_DECEL x dt                 # rolling friction
fuel  -= (BASE + SPEED_FACTOR x speed) x dt # consumption
temp  += (target - temp) x rate x dt        # thermal model
```

---

## 6. Results and Discussion

### 6.1 Feature Completion

| Feature | Status |
|---|---|
| EAR drowsiness detection | Complete |
| MAR yawn detection | Complete |
| Head pose estimation | Complete |
| Emotion classification | Complete |
| Physics vehicle simulation | Complete |
| Automatic gear selection P/N/1-6 | Complete |
| PARK button (instant stop) | Complete |
| Gear colour indicator (grey/green/blue) | Complete |
| 4 adaptive colour themes | Complete |
| Consistent layout across all modes | Complete |
| 5-second debounce for theme changes | Complete |
| Immediate DANGER escalation | Complete |
| Priority-graded audio alarms | Complete |
| Floating alert overlay with auto-dismiss | Complete |
| Auto-drive simulation mode | Complete |

### 6.2 Observed Behaviours

- **No more rapid flickering**: the 5-second debounce prevents the DANGER/ALERT/STANDARD oscillation seen in earlier logs. A new theme must be consistently requested for 5 full seconds before it applies.
- **Safety escalation preserved**: escalation to DANGER (drowsiness + overheating) still applies immediately, never blocking a genuine safety warning.
- **Gear display**: updates smoothly; colour shifts green (1-3) to blue (4-6) to grey (P/N) with each speed band transition.
- **PARK button**: immediately halts simulated vehicle speed and sets gear='P'.
- **Audio alarms**: play asynchronously via daemon threads; the UI remains fully interactive during playback.
- **Layout stability**: all panels (Vehicle Instruments, Driver Monitoring, Driving Behavior, Alerts) remain visible at all times across all themes.

### 6.3 Limitations

1. Webcam-based monitoring may degrade in direct sunlight or very low-light conditions.
2. The vehicle simulator uses Euler integration and does not connect to real OBD-II hardware.
3. The emotion classifier is heuristic-based; a deep-learning model would improve accuracy.
4. Audio latency can vary across platforms depending on OS audio buffer settings.

### 6.4 Future Work

- Real OBD-II integration via python-obd for live vehicle data.
- ML drowsiness model trained on NTHU-DDD or UTA-RLDD datasets.
- Driver voice command support via SpeechRecognition.
- Night-vision support via IR camera module.
- Configurable debounce interval and custom WAV/MP3 alarm sounds.
- Embedded deployment on Raspberry Pi 4 or NVIDIA Jetson Nano.

---

## 7. References

1. WHO (2023). Global Status Report on Road Safety. World Health Organization, Geneva.
2. Soukupova, T. and Cech, J. (2016). Real-Time Eye Blink Detection using Facial Landmarks. 21st Computer Vision Winter Workshop.
3. Abtahi, S., et al. (2014). YawDD: A yawning detection dataset. ACM MMSys 2014, 24-28.
4. Daza, I.G., et al. (2014). Fusion of Optimized Indicators from ADAS for Driver Drowsiness Detection. Sensors, 14(1), 1106-1131.
5. Viola, P. and Jones, M. (2001). Rapid Object Detection using a Boosted Cascade of Simple Features. CVPR 2001, 511-518.
6. Kartynnik, Y., et al. (2019). Real-time Facial Surface Geometry from Monocular Video on Mobile GPUs. CVPR 2019 Workshop.
7. Regan, M.A., et al. (2011). Driver distraction and driver inattention. Accident Analysis and Prevention, 43(5), 1771-1777.
8. Burnett, G. and Donkor, F. (2020). Adaptive driver assistance system interfaces. In Human Factors in Automated Driving. Springer.
9. Engstrom, J., et al. (2005). Effects of visual and cognitive load in real and simulated motorway driving. Transportation Research Part F, 8(2), 97-120.
10. ISO 15008:2017. Road vehicles - Ergonomic aspects of transport information and control systems. ISO, Geneva.
11. Patterson, R.D. (1982). Guidelines for auditory warning systems on civil aircraft. CAA Paper 82017, UK.
12. ISO 11428:1996. Ergonomics - Visual danger signals. ISO, Geneva.
13. Bradski, G. (2000). The OpenCV Library. Dr. Dobb's Journal, 25(11), 120-125.
14. Riverbank Computing (2024). PyQt5 Reference Guide. Riverbank Computing Ltd.
