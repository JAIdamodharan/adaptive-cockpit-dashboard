import { DrowsinessEngine } from './engine.js';

const $ = (id) => document.getElementById(id);
const TASKS_VERSION = '0.10.14';
const WASM = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${TASKS_VERSION}/wasm`;
const MODEL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';

const LEFT = [362, 385, 387, 263, 373, 380];
const RIGHT = [33, 160, 158, 133, 153, 144];
const OVERLAY_PTS = [...LEFT, ...RIGHT, 13, 14, 78, 308];

const engine = new DrowsinessEngine();
let landmarker = null, stream = null, rafId = null, mode = 'idle';
let earWin = [], prevEar = 0.3, prevMar = 0.1;
const vehicle = { speed: 0, rpm: 0, fuel: 78, temp: 40, accel: false, brake: false };

// ---------- helpers ----------
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const eyeEar = (lm, i) => (dist(lm[i[1]], lm[i[5]]) + dist(lm[i[2]], lm[i[4]])) / (2 * dist(lm[i[0]], lm[i[3]]));
const median3 = (a) => [...a].sort((x, y) => x - y)[a.length >> 1];

function poseFromMatrix(m) {
  // column-major 4x4 -> rotation R[r][c] = m[c*4 + r]
  const R = (r, c) => m[c * 4 + r];
  const sy = Math.hypot(R(0, 0), R(1, 0));
  let pitch = Math.atan2(R(2, 1), R(2, 2)) * 180 / Math.PI;
  const yaw = Math.atan2(-R(2, 0), sy) * 180 / Math.PI;
  if (pitch > 90) pitch -= 180; else if (pitch < -90) pitch += 180;
  return [pitch, yaw];
}

// ---------- gauges ----------
function drawGauge(canvas, value, max, title, unit, redline = 0.85, decimals = 0) {
  const ctx = canvas.getContext('2d'), w = canvas.width, h = canvas.height, r = w / 2 - 22;
  ctx.clearRect(0, 0, w, h); ctx.save(); ctx.translate(w / 2, h / 2);
  const frac = Math.max(0, Math.min(1, value / max)), a0 = 135 * Math.PI / 180, sweep = 270 * Math.PI / 180;
  const face = ctx.createRadialGradient(0, 0, 0, 0, 0, r + 12);
  face.addColorStop(0, '#282c38'); face.addColorStop(1, '#0e1016');
  ctx.fillStyle = face; ctx.beginPath(); ctx.arc(0, 0, r + 12, 0, 7); ctx.fill();
  ctx.lineCap = 'round'; ctx.lineWidth = 14;
  ctx.strokeStyle = 'rgba(255,255,255,.1)'; ctx.beginPath(); ctx.arc(0, 0, r, a0, a0 + sweep); ctx.stroke();
  const color = frac < 0.6 ? '#2ecc71' : frac < redline ? '#f1c40f' : '#e74c3c';
  if (frac > 0) { ctx.strokeStyle = color; ctx.shadowColor = color; ctx.shadowBlur = 14; ctx.beginPath(); ctx.arc(0, 0, r, a0, a0 + sweep * frac); ctx.stroke(); ctx.shadowBlur = 0; }
  for (let i = 0; i <= 20; i++) {
    const t = i / 20, a = a0 + sweep * t, big = i % 2 === 0, ro = r - 20, ri = ro - (big ? 12 : 6);
    ctx.strokeStyle = t >= redline ? 'rgba(231,76,60,.8)' : `rgba(255,255,255,${big ? .6 : .28})`; ctx.lineWidth = big ? 2 : 1;
    ctx.beginPath(); ctx.moveTo(ro * Math.cos(a), ro * Math.sin(a)); ctx.lineTo(ri * Math.cos(a), ri * Math.sin(a)); ctx.stroke();
  }
  const na = a0 + sweep * frac; ctx.strokeStyle = '#fff'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(r * .7 * Math.cos(na), r * .7 * Math.sin(na)); ctx.stroke();
  ctx.fillStyle = color; ctx.beginPath(); ctx.arc(0, 0, 7, 0, 7); ctx.fill();
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center';
  ctx.font = 'bold 34px Helvetica, Arial'; ctx.fillText(value.toFixed(decimals), 0, r * .55);
  ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.font = '13px Helvetica, Arial'; ctx.fillText(unit, 0, r * .55 + 20);
  ctx.font = 'bold 13px Helvetica, Arial'; ctx.fillText(title, 0, r * .25); ctx.restore();
}

// ---------- alarm ----------
let audioCtx = null, lastAlarm = -10;
function beep() {
  if (!$('sound').checked) return;
  audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === 'suspended') audioCtx.resume();
  for (let i = 0; i < 3; i++) {
    const o = audioCtx.createOscillator(), g = audioCtx.createGain(), t = audioCtx.currentTime + i * 0.55;
    o.frequency.value = 880; o.type = 'sine'; o.connect(g); g.connect(audioCtx.destination);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(.6, t + .02); g.gain.linearRampToValueAtTime(0, t + .45);
    o.start(t); o.stop(t + .5);
  }
}
function log(msg) {
  const li = document.createElement('li'); li.textContent = `${new Date().toLocaleTimeString()}  ${msg}`;
  $('log').prepend(li); while ($('log').children.length > 30) $('log').lastChild.remove();
}

// ---------- per-frame processing ----------
let lastState = '';
function handle(t, ear, mar, pitch, yaw) {
  const a = engine.update(t, ear, mar, pitch, yaw);
  render(a, ear, mar, pitch, yaw);
  if (a.calibrated && (a.state === 'drowsy' || a.level >= 0.65) && t - lastAlarm >= 2) { lastAlarm = t; beep(); }
  if (a.state !== lastState) { lastState = a.state; log(`State: ${a.state.toUpperCase()}`); }
}

function render(a, ear, mar, pitch, yaw) {
  const state = a.state;
  $('stateText').textContent = a.calibrated ? `DRIVER: ${state.toUpperCase()}` : `CALIBRATING… ${Math.round(a.calibrationProgress * 100)}% (look at the road)`;
  $('stateText').className = state;
  $('badge').textContent = state === 'drowsy' ? 'DROWSY!' : mode === 'idle' ? 'IDLE' : 'LIVE';
  $('badge').classList.toggle('drowsy', state === 'drowsy');
  document.body.dataset.theme = state === 'drowsy' ? 'danger' : state === 'fatigued' ? 'calm' : 'standard';
  $('camera').querySelector('.video-wrap').className = `video-wrap ${state}`;
  const bar = $('drowsyBar'); bar.style.width = `${Math.round(a.level * 100)}%`;
  bar.style.background = a.level < 0.35 ? '#2ecc71' : a.level < 0.65 ? '#f1c40f' : '#e74c3c';
  $('ear').textContent = ear == null ? '–' : ear.toFixed(3);
  $('baseline').textContent = a.baselineEar ? a.baselineEar.toFixed(3) : 'calibrating';
  $('perclos').textContent = `${Math.round(a.perclos * 100)}%`;
  $('mar').textContent = mar == null ? '–' : mar.toFixed(2);
  $('blinks').textContent = a.calibrated ? engine.blinkRatePerMin * 2 : '–';
  $('yawns').textContent = engine.yawnTotal;
  $('pose').textContent = `${pitch.toFixed(0)}° / ${yaw.toFixed(0)}°`;
}

function processLandmarks(t, lm, matrix) {
  const raw = (eyeEar(lm, LEFT) + eyeEar(lm, RIGHT)) / 2;
  earWin.push(raw); if (earWin.length > 3) earWin.shift();
  const ear = 0.6 * median3(earWin) + 0.4 * prevEar; prevEar = ear;
  const marRaw = dist(lm[13], lm[14]) / dist(lm[78], lm[308]);
  const mar = 0.5 * marRaw + 0.5 * prevMar; prevMar = mar;
  const [pitch, yaw] = matrix ? poseFromMatrix(matrix) : [0, 0];
  handle(t, ear, mar, pitch, yaw);
}

// ---------- camera mode ----------
async function startCamera() {
  $('startCam').disabled = true; $('startDemo').disabled = true; $('placeholder').hidden = false;
  $('placeholder').textContent = 'Loading face model…';
  try {
    if (!landmarker) {
      const { FaceLandmarker, FilesetResolver } = await import(`https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${TASKS_VERSION}/vision_bundle.mjs`);
      const fileset = await FilesetResolver.forVisionTasks(WASM);
      landmarker = await FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL, delegate: 'GPU' }, runningMode: 'VIDEO', numFaces: 1,
        outputFacialTransformationMatrixes: true,
      });
    }
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: 'user' }, audio: false });
  } catch (e) {
    $('placeholder').textContent = e.name === 'NotAllowedError' ? 'Camera permission denied' : `Could not start: ${e.message}`;
    $('startCam').disabled = false; $('startDemo').disabled = false; log(`Camera error: ${e.message}`); return;
  }
  const v = $('video'); v.srcObject = stream; await v.play();
  $('placeholder').hidden = true; $('overlay').width = v.videoWidth; $('overlay').height = v.videoHeight;
  engine.reset(); earWin = []; lastState = '';
  setMode('camera'); loopCamera();
}

let lastVideoTime = -1;
function loopCamera() {
  const v = $('video');
  if (v.currentTime !== lastVideoTime && v.readyState >= 2) {
    lastVideoTime = v.currentTime;
    const t = performance.now() / 1000;
    const res = landmarker.detectForVideo(v, performance.now());
    const ov = $('overlay'), ctx = ov.getContext('2d'); ctx.clearRect(0, 0, ov.width, ov.height);
    if (res.faceLandmarks && res.faceLandmarks.length) {
      const lm = res.faceLandmarks[0];
      ctx.fillStyle = '#00e5ff';
      for (const i of OVERLAY_PTS) { ctx.beginPath(); ctx.arc(lm[i].x * ov.width, lm[i].y * ov.height, 2.5, 0, 7); ctx.fill(); }
      const mtx = res.facialTransformationMatrixes && res.facialTransformationMatrixes[0] ? res.facialTransformationMatrixes[0].data : null;
      processLandmarks(t, lm, mtx);
    } else {
      render(engine.update(t, null), null, null, 0, 0); // lost face never counts as closed eyes
    }
  }
  rafId = requestAnimationFrame(loopCamera);
}

// ---------- demo mode (simulated driver) ----------
let demoStart = 0;
function loopDemo() {
  const t = (performance.now() - demoStart) / 1000;
  const phase = t % 70;                       // 0-14 s alert, 14-50 s drowsy, 50-70 s recovery
  let closed;
  if (phase < 14 || phase >= 50) closed = (t % 3.5) < 0.18;
  else closed = (t % 4) < 1.3;
  const ear = (closed ? 0.10 : 0.30) + (Math.random() - .5) * 0.02;
  const mar = phase > 24 && phase < 27 ? 0.7 : 0.1;
  handle(t, ear, mar, (Math.random() - .5) * 4, (Math.random() - .5) * 6);
  rafId = requestAnimationFrame(loopDemo);
}

// ---------- vehicle sim ----------
let lastTick = performance.now();
function vehicleTick() {
  const now = performance.now(), dt = (now - lastTick) / 1000; lastTick = now;
  if (vehicle.accel) vehicle.speed += 28 * dt; else if (vehicle.brake) vehicle.speed -= 55 * dt; else vehicle.speed -= 6 * dt;
  vehicle.speed = Math.max(0, Math.min(200, vehicle.speed));
  vehicle.fuel = Math.max(0, vehicle.fuel - vehicle.speed * 0.0024 * dt);
  vehicle.temp += ((40 + vehicle.speed * 0.35) - vehicle.temp) * dt * 0.2;
  drawGauge($('speedGauge'), vehicle.speed, 200, 'SPEED', 'km/h');
  drawGauge($('drowsyGauge'), engine.last.level * 100, 100, 'DROWSINESS', '%', 0.65);
  $('fuelBar').style.width = `${vehicle.fuel}%`; $('fuelBar').style.background = vehicle.fuel < 20 ? '#e74c3c' : '#2ecc71';
  $('tempBar').style.width = `${Math.min(100, vehicle.temp / 1.2)}%`; $('tempBar').style.background = vehicle.temp > 95 ? '#e74c3c' : '#2ecc71';
  requestAnimationFrame(vehicleTick);
}
for (const key of ['accel', 'brake']) {
  const b = $(key);
  b.addEventListener('pointerdown', (e) => { e.preventDefault(); vehicle[key] = true; });
  for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) b.addEventListener(ev, () => { vehicle[key] = false; });
}

// ---------- mode / controls ----------
function setMode(m) {
  mode = m;
  $('stop').disabled = m === 'idle'; $('recal').disabled = m === 'idle';
  $('startCam').disabled = m !== 'idle'; $('startDemo').disabled = m !== 'idle';
  $('badge').textContent = m === 'idle' ? 'IDLE' : 'LIVE';
}
function stop() {
  cancelAnimationFrame(rafId); rafId = null;
  if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
  $('video').srcObject = null; $('placeholder').hidden = false; $('placeholder').textContent = 'Camera off';
  const ov = $('overlay'); ov.getContext('2d').clearRect(0, 0, ov.width, ov.height);
  engine.reset(); earWin = []; lastState = ''; setMode('idle');
  render(engine.last, null, null, 0, 0); $('stateText').textContent = 'Start the camera to begin'; $('stateText').className = '';
  document.body.dataset.theme = 'standard';
}
$('startCam').onclick = startCamera;
$('startDemo').onclick = () => {
  engine.reset(); lastState = ''; demoStart = performance.now();
  $('placeholder').hidden = false; $('placeholder').textContent = 'Demo: simulated driver';
  setMode('demo'); loopDemo();
};
$('stop').onclick = stop;
$('recal').onclick = () => { engine.reset(); earWin = []; lastState = ''; log('Recalibrating'); };

vehicleTick();
