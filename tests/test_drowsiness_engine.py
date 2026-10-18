import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from drowsiness_engine import DrowsinessEngine, PerclosWindow, YawnDetector, DrowsinessConfig

FPS = 10
DT = 1.0 / FPS


def run(engine, start, seconds, ear_fn, mar=0.1, pitch=0.0, yaw=0.0):
    t = start
    result = None
    for _ in range(int(seconds * FPS)):
        result = engine.update(t, ear_fn(t), mar=mar, pitch=pitch, yaw=yaw)
        t += DT
    return t, result


def calibrated_engine(baseline=0.30, seed=1):
    rnd = random.Random(seed)
    e = DrowsinessEngine()
    t, r = run(e, 0.0, 12, lambda _t: baseline + rnd.uniform(-0.01, 0.01))
    assert r.calibrated
    return e, t


def test_no_alert_during_calibration():
    e = DrowsinessEngine()
    # eyes shut from the very first frame must not alert while calibrating
    _, r = run(e, 0.0, 5, lambda t: 0.10)
    assert r.state == "calibrating" and r.level == 0.0


def test_baseline_is_personal():
    e, _ = calibrated_engine(baseline=0.24)
    assert abs(e.baseline_ear - 0.24) < 0.03


def test_normal_blinking_stays_normal():
    e, t = calibrated_engine()
    # 0.2 s blink every 3 s for 60 s
    def ear(tt):
        return 0.10 if (tt % 3.0) < 0.2 else 0.30
    t, r = run(e, t, 60, ear)
    assert r.state == "normal"
    assert r.perclos < 0.15


def test_long_closures_become_drowsy():
    e, t = calibrated_engine()
    # 1.2 s eye closure every 3 s
    def ear(tt):
        return 0.10 if (tt % 3.0) < 1.2 else 0.30
    t, r = run(e, t, 45, ear)
    assert r.state == "drowsy"


def test_microsleep_triggers_immediately():
    e, t = calibrated_engine()
    t, r = run(e, t, 2.0, lambda tt: 0.10)
    assert r.microsleep and r.state == "drowsy"


def test_lost_face_never_counts_as_closed():
    e, t = calibrated_engine()
    t, r = run(e, t, 30, lambda tt: None)
    assert r.state == "normal" and r.perclos == 0.0


def test_extreme_head_turn_frames_ignored():
    e, t = calibrated_engine()
    t, r = run(e, t, 20, lambda tt: 0.05, yaw=60.0)
    assert r.state == "normal"


def test_recovery_and_hysteresis():
    e, t = calibrated_engine()
    t, r = run(e, t, 4, lambda tt: 0.10)
    assert r.state == "drowsy"
    t, r = run(e, t, 120, lambda tt: 0.30)
    assert r.state == "normal"


def test_yawn_needs_duration():
    cfg = DrowsinessConfig()
    y = YawnDetector(cfg)
    for i in range(5):  # 0.5 s open mouth: talking, not a yawn
        y.update(i * DT, 0.7)
    y.update(0.6, 0.1)
    assert y.recent_count == 0
    t = 10.0
    for i in range(20):  # 2 s open mouth
        y.update(t + i * DT, 0.7)
    assert y.recent_count == 1


def test_perclos_time_weighted():
    w = PerclosWindow(60)
    for i in range(300):
        w.add(i * 0.1, i % 2 == 0)
    assert 0.4 < w.ratio() < 0.6


def test_vehicle_fusion_escalates_fatigue():
    from types import SimpleNamespace
    from decision_engine import AdaptiveDecisionEngine
    de = AdaptiveDecisionEngine()
    de.driver_state = SimpleNamespace(state_classification="fatigued")
    de.behavior_state = SimpleNamespace(risk_index=0.1, stability_score=0.9)
    assert de._driver_class() == "fatigued"
    de.behavior_state = SimpleNamespace(risk_index=0.7, stability_score=0.9)
    assert de._driver_class() == "drowsy"


def test_no_false_alarm_right_after_calibration():
    # Regression: a closed frame just after calibration used to read as PERCLOS 100%
    e, t = calibrated_engine()
    t, r = run(e, t, 0.4, lambda tt: 0.10)
    assert r.state == "normal"
    t, r = run(e, t, 5, lambda tt: 0.30)
    assert r.state == "normal"
