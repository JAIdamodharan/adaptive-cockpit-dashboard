import test from 'node:test';
import assert from 'node:assert/strict';
import { DrowsinessEngine } from './engine.js';

const DT = 0.1;
function run(e, t0, secs, earFn, o = {}) {
  let t = t0, r;
  for (let i = 0; i < secs / DT; i++, t += DT) r = e.update(t, earFn(t), o.mar ?? 0.1, o.pitch ?? 0, o.yaw ?? 0);
  return [t, r];
}
function calibrated() {
  const e = new DrowsinessEngine(); let n = 0;
  const [t, r] = run(e, 0, 12, () => 0.30 + ((n++ % 5) - 2) * 0.004);
  assert.ok(r.calibrated); return [e, t];
}

test('no alert while calibrating', () => { const e = new DrowsinessEngine(); const [, r] = run(e, 0, 5, () => 0.1); assert.equal(r.state, 'calibrating'); });
test('normal blinking stays normal', () => { const [e, t] = calibrated(); const [, r] = run(e, t, 60, (x) => (x % 3 < 0.2 ? 0.1 : 0.3)); assert.equal(r.state, 'normal'); });
test('long closures become drowsy', () => { const [e, t] = calibrated(); const [, r] = run(e, t, 45, (x) => (x % 3 < 1.2 ? 0.1 : 0.3)); assert.equal(r.state, 'drowsy'); });
test('microsleep is immediate', () => { const [e, t] = calibrated(); const [, r] = run(e, t, 2, () => 0.1); assert.ok(r.microsleep); assert.equal(r.state, 'drowsy'); });
test('lost face is never closed eyes', () => { const [e, t] = calibrated(); const [, r] = run(e, t, 30, () => null); assert.equal(r.state, 'normal'); });
test('no false alarm right after calibration', () => { const [e, t] = calibrated(); let [t2, r] = run(e, t, 0.4, () => 0.1); assert.equal(r.state, 'normal'); [, r] = run(e, t2, 5, () => 0.3); assert.equal(r.state, 'normal'); });
test('recovers', () => { const [e, t] = calibrated(); let [t2, r] = run(e, t, 4, () => 0.1); assert.equal(r.state, 'drowsy'); [, r] = run(e, t2, 120, () => 0.3); assert.equal(r.state, 'normal'); });
