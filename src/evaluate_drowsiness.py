"""Offline evaluation of the drowsiness engine.

Usage:
    python evaluate_drowsiness.py --synthetic
    python evaluate_drowsiness.py --csv features.csv

CSV columns: t,ear,mar,pitch,yaw,label   (label: 1 = drowsy segment, 0 = alert;
empty ear = face lost). Extract the per-frame features from a labelled dataset such
as NTHU-DDD or UTA-RLDD using the same landmark code as the monitor, then evaluate
here to tune thresholds with real numbers.

Reports frame-level precision / recall / F1 on the 'drowsy' state and false alarms
per hour of alert driving (after calibration).
"""

import argparse
import csv
import random

from drowsiness_engine import DrowsinessEngine


def synthetic(seed=0, minutes=6):
    """Alert driver (blinks) followed by a drowsy driver (long closures, yawns)."""
    rnd = random.Random(seed)
    t, rows = 0.0, []
    for phase, label in ((minutes * 60 // 2, 0), (minutes * 60 // 2, 1)):
        end = t + phase
        while t < end:
            if label == 0:
                closed = (t % 3.5) < 0.18
            else:
                closed = (t % 4.0) < rnd.uniform(0.7, 1.4)
            ear = (0.10 if closed else 0.30) + rnd.uniform(-0.015, 0.015)
            mar = 0.7 if label and (t % 40) < 2.0 else 0.1
            rows.append((t, ear, mar, rnd.uniform(-3, 3), rnd.uniform(-5, 5), label))
            t += 0.1
    return rows


def load_csv(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            ear = float(r["ear"]) if r["ear"] not in ("", "None") else None
            rows.append((float(r["t"]), ear, float(r["mar"] or 0), float(r["pitch"] or 0),
                         float(r["yaw"] or 0), int(r["label"])))
    return rows


def evaluate(rows, drowsy_states=("drowsy",)):
    engine = DrowsinessEngine()
    tp = fp = fn = tn = 0
    false_alarm_events = 0
    prev_alarm = False
    alert_seconds = 0.0
    last_t = rows[0][0]
    for t, ear, mar, pitch, yaw, label in rows:
        a = engine.update(t, ear, mar, pitch, yaw)
        if not a.calibrated:
            last_t = t
            continue
        pred = a.state in drowsy_states
        if pred and label:
            tp += 1
        elif pred and not label:
            fp += 1
        elif not pred and label:
            fn += 1
        else:
            tn += 1
        if not label:
            alert_seconds += t - last_t
            if pred and not prev_alarm:
                false_alarm_events += 1
        prev_alarm = pred and not label
        last_t = t
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    fa_per_hour = false_alarm_events / (alert_seconds / 3600.0) if alert_seconds else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "false_alarms_per_hour": fa_per_hour,
            "frames": tp + fp + fn + tn}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--synthetic", action="store_true")
    args = ap.parse_args()
    data = load_csv(args.csv) if args.csv else synthetic()
    for k, v in evaluate(data).items():
        print(f"{k:>24}: {v:.3f}" if isinstance(v, float) else f"{k:>24}: {v}")
