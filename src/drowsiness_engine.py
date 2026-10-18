"""Drowsiness estimation engine.

Pure-Python (no OpenCV / Qt) so it can be unit tested with synthetic signals.
All methods take an explicit timestamp in seconds.

Pipeline
--------
1. ``EarCalibrator``  learns the driver's own open-eye EAR (and neutral head pose)
   during a short warm-up, so thresholds are relative instead of a fixed 0.20.
2. ``BlinkTracker``   separates normal blinks (< 0.5 s) from long closures and
   micro-sleeps, and measures blink duration.
3. ``PerclosWindow``  time-weighted share of the last minute with eyes closed.
4. ``YawnDetector``   duration-based yawn events from the mouth aspect ratio.
5. ``DrowsinessEngine`` fuses all cues into one score with hysteresis, and
   stays silent until calibration has finished.
"""

from collections import deque
from dataclasses import dataclass, field
from statistics import median
from typing import Deque, Dict, Optional, Tuple


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class DrowsinessConfig:
    # Calibration
    calibration_seconds: float = 10.0
    min_calibration_samples: int = 20
    baseline_percentile: float = 0.75       # robust to blinks inside calibration
    baseline_clamp: Tuple[float, float] = (0.18, 0.45)
    baseline_adapt_rate: float = 0.002      # slow drift correction while eyes open

    # Eye closure (relative to the driver's own baseline, with hysteresis)
    closed_ratio: float = 0.70              # closed when EAR < baseline * 0.70
    reopen_ratio: float = 0.80              # open again when EAR > baseline * 0.80

    # Closure classification (seconds)
    min_blink_s: float = 0.05
    long_closure_s: float = 0.50
    microsleep_s: float = 1.50

    # Windows (seconds)
    perclos_window_s: float = 60.0
    event_window_s: float = 60.0
    yawn_window_s: float = 300.0

    # Yawn: mouth open long enough
    yawn_mar: float = 0.55
    yawn_min_s: float = 1.2

    # Head pose (degrees, relative to neutral pose captured during calibration)
    head_down_deg: float = 15.0
    max_yaw_for_valid_deg: float = 35.0

    # Component weights (sum to 1)
    w_perclos: float = 0.40
    w_long_closures: float = 0.20
    w_blink_duration: float = 0.10
    w_yawns: float = 0.15
    w_head_down: float = 0.15

    # Score smoothing and hysteresis
    rise_alpha: float = 0.35
    fall_alpha: float = 0.08
    fatigued_enter: float = 0.35
    fatigued_exit: float = 0.25
    drowsy_enter: float = 0.65
    drowsy_exit: float = 0.50


@dataclass
class DrowsinessAssessment:
    level: float = 0.0                      # 0.0 alert .. 1.0 drowsy
    state: str = "calibrating"              # calibrating | normal | fatigued | drowsy
    calibrated: bool = False
    calibration_progress: float = 0.0       # 0..1
    perclos: float = 0.0
    baseline_ear: Optional[float] = None
    closure_s: float = 0.0                  # current ongoing closure
    microsleep: bool = False
    components: Dict[str, float] = field(default_factory=dict)


class EarCalibrator:
    """Learns the driver's open-eye EAR and neutral head pitch/yaw."""

    def __init__(self, cfg: DrowsinessConfig):
        self.cfg = cfg
        self.reset()

    def reset(self):
        self._start: Optional[float] = None
        self._ears = []
        self._pitches = []
        self._yaws = []
        self.baseline: Optional[float] = None
        self.neutral_pitch = 0.0
        self.neutral_yaw = 0.0

    @property
    def done(self) -> bool:
        return self.baseline is not None

    def progress(self, now: float) -> float:
        if self.done:
            return 1.0
        if self._start is None:
            return 0.0
        return _clip01((now - self._start) / self.cfg.calibration_seconds)

    def add(self, t: float, ear: float, pitch: float, yaw: float) -> bool:
        """Feed a *valid* frame. Returns True the moment calibration completes."""
        if self.done:
            return False
        if self._start is None:
            self._start = t
        self._ears.append(ear)
        self._pitches.append(pitch)
        self._yaws.append(yaw)
        if (t - self._start >= self.cfg.calibration_seconds
                and len(self._ears) >= self.cfg.min_calibration_samples):
            ordered = sorted(self._ears)
            idx = min(len(ordered) - 1, int(len(ordered) * self.cfg.baseline_percentile))
            lo, hi = self.cfg.baseline_clamp
            self.baseline = max(lo, min(hi, ordered[idx]))
            self.neutral_pitch = median(self._pitches)
            self.neutral_yaw = median(self._yaws)
            return True
        return False

    def adapt(self, ear: float):
        """Very slow drift correction using confidently-open eyes."""
        if self.baseline is not None and ear > self.baseline * self.cfg.reopen_ratio:
            a = self.cfg.baseline_adapt_rate
            lo, hi = self.cfg.baseline_clamp
            self.baseline = max(lo, min(hi, (1 - a) * self.baseline + a * ear))


class BlinkTracker:
    """Closed/open state machine with hysteresis and duration classification."""

    def __init__(self, cfg: DrowsinessConfig):
        self.cfg = cfg
        self.reset()

    def reset(self):
        self.closed = False
        self._closed_since: Optional[float] = None
        self.blinks: Deque[Tuple[float, float]] = deque()          # (end_time, duration)
        self.long_closures: Deque[Tuple[float, float]] = deque()   # (end_time, duration)

    def update(self, t: float, ear: float, baseline: float) -> float:
        """Returns the duration of the ongoing closure (0 if eyes are open)."""
        close_thr = baseline * self.cfg.closed_ratio
        open_thr = baseline * self.cfg.reopen_ratio
        if not self.closed and ear < close_thr:
            self.closed = True
            self._closed_since = t
        elif self.closed and ear > open_thr:
            duration = t - (self._closed_since or t)
            self.closed = False
            self._closed_since = None
            if duration >= self.cfg.long_closure_s:
                self.long_closures.append((t, duration))
            elif duration >= self.cfg.min_blink_s:
                self.blinks.append((t, duration))
        self._prune(t)
        return (t - self._closed_since) if self.closed and self._closed_since is not None else 0.0

    def _prune(self, t: float):
        horizon = t - self.cfg.event_window_s
        while self.blinks and self.blinks[0][0] < horizon:
            self.blinks.popleft()
        while self.long_closures and self.long_closures[0][0] < horizon:
            self.long_closures.popleft()

    @property
    def blink_rate_per_min(self) -> float:
        return float(len(self.blinks) + len(self.long_closures))

    @property
    def mean_blink_duration(self) -> Optional[float]:
        if len(self.blinks) < 3:
            return None
        return sum(d for _, d in self.blinks) / len(self.blinks)


class PerclosWindow:
    """Time-weighted fraction of a sliding window spent in a given flag state."""

    def __init__(self, window_s: float, max_gap_s: float = 1.0, min_span_s: float = 15.0):
        self.window_s = window_s
        self.max_gap_s = max_gap_s
        # Ratios over a very short history are meaningless (one closed frame would read
        # as 100%), so report 0 until enough time has been observed.
        self.min_span_s = min_span_s
        self._samples: Deque[Tuple[float, bool]] = deque()

    def reset(self):
        self._samples.clear()

    def add(self, t: float, flag: bool):
        self._samples.append((t, flag))
        horizon = t - self.window_s
        while len(self._samples) > 2 and self._samples[1][0] < horizon:
            self._samples.popleft()

    def ratio(self) -> float:
        if len(self._samples) < 2:
            return 0.0
        if self._samples[-1][0] - self._samples[0][0] < self.min_span_s:
            return 0.0
        total = flagged = 0.0
        prev_t, prev_f = self._samples[0]
        for t, f in list(self._samples)[1:]:
            dt = min(t - prev_t, self.max_gap_s)
            total += dt
            if prev_f:
                flagged += dt
            prev_t, prev_f = t, f
        return flagged / total if total > 0 else 0.0


class YawnDetector:
    """Counts yawns: mouth wide open continuously for ``yawn_min_s``."""

    def __init__(self, cfg: DrowsinessConfig):
        self.cfg = cfg
        self.reset()

    def reset(self):
        self._open_since: Optional[float] = None
        self._counted = False
        self.events: Deque[float] = deque()

    def update(self, t: float, mar: float) -> bool:
        """Returns True when a new yawn is registered."""
        new = False
        if mar > self.cfg.yawn_mar:
            if self._open_since is None:
                self._open_since = t
            if not self._counted and t - self._open_since >= self.cfg.yawn_min_s:
                self.events.append(t)
                self._counted = True
                new = True
        else:
            self._open_since = None
            self._counted = False
        horizon = t - self.cfg.yawn_window_s
        while self.events and self.events[0] < horizon:
            self.events.popleft()
        return new

    @property
    def recent_count(self) -> int:
        return len(self.events)


class DrowsinessEngine:
    """Fuses PERCLOS, closure events, blink duration, yawns and head pose."""

    def __init__(self, cfg: Optional[DrowsinessConfig] = None):
        self.cfg = cfg or DrowsinessConfig()
        self.calibrator = EarCalibrator(self.cfg)
        self.blinks = BlinkTracker(self.cfg)
        self.perclos = PerclosWindow(self.cfg.perclos_window_s)
        self.head_down = PerclosWindow(self.cfg.perclos_window_s)
        self.yawns = YawnDetector(self.cfg)
        self.reset()

    def reset(self):
        self.calibrator.reset()
        self.blinks.reset()
        self.perclos.reset()
        self.head_down.reset()
        self.yawns.reset()
        self._score = 0.0
        self._state = "calibrating"
        self.last = DrowsinessAssessment()

    @property
    def baseline_ear(self) -> Optional[float]:
        return self.calibrator.baseline

    @property
    def blink_rate_per_min(self) -> float:
        return self.blinks.blink_rate_per_min

    @property
    def yawn_count(self) -> int:
        return self.yawns.recent_count

    # ------------------------------------------------------------------
    def update(self, t: float, ear: Optional[float], mar: float = 0.0,
               pitch: float = 0.0, yaw: float = 0.0) -> DrowsinessAssessment:
        """Process one frame.

        ``ear=None`` means the frame was unusable (face lost, extreme head turn,
        bad lighting). Such frames never count as closed eyes: the score just
        decays slowly.
        """
        cfg = self.cfg
        yaw_dev = abs(yaw - self.calibrator.neutral_yaw)
        valid = ear is not None and yaw_dev <= cfg.max_yaw_for_valid_deg

        if not valid:
            return self._finish(t, valid=False)

        # Calibration phase: learn the person, never alert
        if not self.calibrator.done:
            self.calibrator.add(t, ear, pitch, yaw)
            self.yawns.update(t, mar)
            return self._finish(t, valid=True)

        baseline = self.calibrator.baseline
        closure_s = self.blinks.update(t, ear, baseline)
        self.perclos.add(t, self.blinks.closed)
        self.yawns.update(t, mar)
        self.head_down.add(t, abs(pitch - self.calibrator.neutral_pitch) > cfg.head_down_deg)
        if not self.blinks.closed:
            self.calibrator.adapt(ear)
        return self._finish(t, valid=True, closure_s=closure_s)

    # ------------------------------------------------------------------
    def _components(self) -> Dict[str, float]:
        perclos = self.perclos.ratio()
        mean_dur = self.blinks.mean_blink_duration
        return {
            "perclos": _clip01((perclos - 0.08) / (0.30 - 0.08)),
            "long_closures": _clip01(len(self.blinks.long_closures) / 3.0),
            "blink_duration": 0.0 if mean_dur is None else _clip01((mean_dur - 0.20) / 0.20),
            "yawns": _clip01(self.yawns.recent_count / 3.0),
            "head_down": _clip01(self.head_down.ratio() / 0.20),
        }

    def _finish(self, t: float, valid: bool, closure_s: float = 0.0) -> DrowsinessAssessment:
        cfg = self.cfg

        if not self.calibrator.done:
            self.last = DrowsinessAssessment(
                level=0.0, state="calibrating", calibrated=False,
                calibration_progress=self.calibrator.progress(t))
            return self.last

        comps = self._components()
        target = (cfg.w_perclos * comps["perclos"]
                  + cfg.w_long_closures * comps["long_closures"]
                  + cfg.w_blink_duration * comps["blink_duration"]
                  + cfg.w_yawns * comps["yawns"]
                  + cfg.w_head_down * comps["head_down"])

        # PERCLOS >= 30% is strong standalone evidence of drowsiness
        if self.perclos.ratio() >= 0.30:
            target = max(target, 0.75)

        microsleep = closure_s >= cfg.microsleep_s
        if microsleep:
            target = max(target, 0.9)
        if not valid:
            target = 0.0  # unusable frame: decay, never escalate

        alpha = cfg.rise_alpha if target > self._score else cfg.fall_alpha
        self._score += alpha * (target - self._score)
        self._score = _clip01(self._score)
        if microsleep:
            self._score = max(self._score, cfg.drowsy_enter)

        self._state = self._next_state(self._score)
        self.last = DrowsinessAssessment(
            level=self._score, state=self._state, calibrated=True,
            calibration_progress=1.0, perclos=self.perclos.ratio(),
            baseline_ear=self.calibrator.baseline, closure_s=closure_s,
            microsleep=microsleep, components=comps)
        return self.last

    def _next_state(self, score: float) -> str:
        cfg = self.cfg
        s = self._state
        if s in ("calibrating", "normal"):
            if score >= cfg.drowsy_enter:
                return "drowsy"
            return "fatigued" if score >= cfg.fatigued_enter else "normal"
        if s == "fatigued":
            if score >= cfg.drowsy_enter:
                return "drowsy"
            return "normal" if score < cfg.fatigued_exit else "fatigued"
        # drowsy
        if score < cfg.drowsy_exit:
            return "fatigued" if score >= cfg.fatigued_exit else "normal"
        return "drowsy"
