// Port of src/drowsiness_engine.py (kept in sync: same thresholds and logic).
const clip01 = (x) => Math.max(0, Math.min(1, x));
const median = (a) => { const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

export const DEFAULT_CONFIG = {
  calibrationSeconds: 10, minCalibrationSamples: 20, baselinePercentile: 0.75,
  baselineClamp: [0.18, 0.45], baselineAdaptRate: 0.002,
  closedRatio: 0.70, reopenRatio: 0.80,
  minBlinkS: 0.05, longClosureS: 0.5, microsleepS: 1.5,
  perclosWindowS: 30, eventWindowS: 30, yawnWindowS: 300,
  yawnMar: 0.55, yawnMinS: 1.2,
  headDownDeg: 15, maxYawForValidDeg: 35,
  wPerclos: 0.40, wLongClosures: 0.20, wBlinkDuration: 0.10, wYawns: 0.15, wHeadDown: 0.15,
  riseTauS: 1.0, fallTauS: 4.0,
  fatiguedEnter: 0.35, fatiguedExit: 0.25, drowsyEnter: 0.65, drowsyExit: 0.50,
};

class FlagWindow {
  constructor(windowS, maxGapS = 1, minSpanS = 15) { this.windowS = windowS; this.maxGapS = maxGapS; this.minSpanS = minSpanS; this.s = []; }
  reset() { this.s = []; }
  add(t, flag) {
    this.s.push([t, flag]);
    const horizon = t - this.windowS;
    while (this.s.length > 2 && this.s[1][0] < horizon) this.s.shift();
  }
  ratio() {
    if (this.s.length < 2) return 0;
    if (this.s[this.s.length - 1][0] - this.s[0][0] < this.minSpanS) return 0;
    let total = 0, flagged = 0, [pt, pf] = this.s[0];
    for (let i = 1; i < this.s.length; i++) {
      const [t, f] = this.s[i]; const dt = Math.min(t - pt, this.maxGapS);
      total += dt; if (pf) flagged += dt; pt = t; pf = f;
    }
    return total > 0 ? flagged / total : 0;
  }
}

export class DrowsinessEngine {
  constructor(cfg = {}) {
    this.cfg = { ...DEFAULT_CONFIG, ...cfg };
    this.perclos = new FlagWindow(this.cfg.perclosWindowS);
    this.headDown = new FlagWindow(this.cfg.perclosWindowS);
    this.reset();
  }
  reset() {
    this.perclos.reset(); this.headDown.reset();
    this.cal = { start: null, ears: [], pitches: [], yaws: [], baseline: null, neutralPitch: 0, neutralYaw: 0 };
    this.closed = false; this.closedSince = null; this.blinks = []; this.longClosures = [];
    this.yawnOpenSince = null; this.yawnCounted = false; this.yawnEvents = []; this.yawnTotal = 0;
    this.score = 0; this.lastT = null; this.state = 'calibrating';
    this.last = { level: 0, state: 'calibrating', calibrated: false, calibrationProgress: 0, perclos: 0, baselineEar: null, closureS: 0, microsleep: false, components: {} };
  }
  get blinkRatePerMin() { return this.blinks.length + this.longClosures.length; }

  update(t, ear, mar = 0, pitch = 0, yaw = 0) {
    const c = this.cfg, cal = this.cal;
    const yawDev = Math.abs(yaw - cal.neutralYaw);
    const valid = ear != null && yawDev <= c.maxYawForValidDeg;
    if (!valid) return this._finish(t, false, 0);

    if (cal.baseline == null) {
      if (cal.start == null) cal.start = t;
      cal.ears.push(ear); cal.pitches.push(pitch); cal.yaws.push(yaw);
      this._yawn(t, mar);
      if (t - cal.start >= c.calibrationSeconds && cal.ears.length >= c.minCalibrationSamples) {
        const o = [...cal.ears].sort((a, b) => a - b);
        const idx = Math.min(o.length - 1, Math.floor(o.length * c.baselinePercentile));
        cal.baseline = Math.max(c.baselineClamp[0], Math.min(c.baselineClamp[1], o[idx]));
        cal.neutralPitch = median(cal.pitches); cal.neutralYaw = median(cal.yaws);
      }
      return this._finish(t, true, 0);
    }

    const closureS = this._blink(t, ear, cal.baseline);
    this.perclos.add(t, this.closed);
    this._yawn(t, mar);
    this.headDown.add(t, Math.abs(pitch - cal.neutralPitch) > c.headDownDeg);
    if (!this.closed && ear > cal.baseline * c.reopenRatio) {
      const a = c.baselineAdaptRate;
      cal.baseline = Math.max(c.baselineClamp[0], Math.min(c.baselineClamp[1], (1 - a) * cal.baseline + a * ear));
    }
    return this._finish(t, true, closureS);
  }

  _blink(t, ear, baseline) {
    const c = this.cfg;
    if (!this.closed && ear < baseline * c.closedRatio) { this.closed = true; this.closedSince = t; }
    else if (this.closed && ear > baseline * c.reopenRatio) {
      const d = t - this.closedSince; this.closed = false; this.closedSince = null;
      if (d >= c.longClosureS) this.longClosures.push([t, d]);
      else if (d >= c.minBlinkS) this.blinks.push([t, d]);
    }
    const h = t - c.eventWindowS;
    this.blinks = this.blinks.filter(([x]) => x >= h);
    this.longClosures = this.longClosures.filter(([x]) => x >= h);
    return this.closed ? t - this.closedSince : 0;
  }

  _yawn(t, mar) {
    const c = this.cfg;
    if (mar > c.yawnMar) {
      if (this.yawnOpenSince == null) this.yawnOpenSince = t;
      if (!this.yawnCounted && t - this.yawnOpenSince >= c.yawnMinS) { this.yawnEvents.push(t); this.yawnCounted = true; this.yawnTotal++; }
    } else { this.yawnOpenSince = null; this.yawnCounted = false; }
    this.yawnEvents = this.yawnEvents.filter((x) => x >= t - c.yawnWindowS);
  }

  _components() {
    const pc = this.perclos.ratio();
    const meanDur = this.blinks.length >= 3 ? this.blinks.reduce((a, [, d]) => a + d, 0) / this.blinks.length : null;
    return {
      perclos: clip01((pc - 0.08) / (0.30 - 0.08)),
      longClosures: clip01(this.longClosures.length / 2),
      blinkDuration: meanDur == null ? 0 : clip01((meanDur - 0.20) / 0.20),
      yawns: clip01(this.yawnEvents.length / 3),
      headDown: clip01(this.headDown.ratio() / 0.20),
    };
  }

  _finish(t, valid, closureS) {
    const c = this.cfg, cal = this.cal;
    if (cal.baseline == null) {
      const p = cal.start == null ? 0 : clip01((t - cal.start) / c.calibrationSeconds);
      return (this.last = { level: 0, state: 'calibrating', calibrated: false, calibrationProgress: p, perclos: 0, baselineEar: null, closureS: 0, microsleep: false, components: {} });
    }
    const k = this._components();
    let target = c.wPerclos * k.perclos + c.wLongClosures * k.longClosures + c.wBlinkDuration * k.blinkDuration + c.wYawns * k.yawns + c.wHeadDown * k.headDown;
    if (this.perclos.ratio() >= 0.30) target = Math.max(target, 0.75);
    const microsleep = closureS >= c.microsleepS;
    if (microsleep) target = Math.max(target, 0.9);
    if (!valid) target = 0;
    const dt = this.lastT != null ? Math.max(0, Math.min(1, t - this.lastT)) : 0.1;
    this.lastT = t;
    const tau = target > this.score ? c.riseTauS : c.fallTauS;
    this.score = clip01(this.score + (1 - Math.exp(-dt / tau)) * (target - this.score));
    if (microsleep) this.score = Math.max(this.score, c.drowsyEnter);
    this.state = this._next(this.score);
    return (this.last = { level: this.score, state: this.state, calibrated: true, calibrationProgress: 1, perclos: this.perclos.ratio(), baselineEar: cal.baseline, closureS, microsleep, components: k });
  }

  _next(score) {
    const c = this.cfg, s = this.state;
    if (s === 'calibrating' || s === 'normal') return score >= c.drowsyEnter ? 'drowsy' : score >= c.fatiguedEnter ? 'fatigued' : 'normal';
    if (s === 'fatigued') return score >= c.drowsyEnter ? 'drowsy' : score < c.fatiguedExit ? 'normal' : 'fatigued';
    return score < c.drowsyExit ? (score >= c.fatiguedExit ? 'fatigued' : 'normal') : 'drowsy';
  }
}
