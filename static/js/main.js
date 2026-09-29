// static/js/main.js
// Dashboard SocketIO client, session management, UI updates

// ── Emotion config ────────────────────────────────────────────────────────────
const EMOTIONS_LIST = ['angry','disgust','fear','happy','sad','surprise','neutral'];
const EMOTION_EMOJIS = { happy:'😄', sad:'😢', angry:'😠', fear:'😨', disgust:'🤢', surprise:'😲', neutral:'😐' };
const EMOTION_COLORS_MAP = {
  happy:'#FFD700', sad:'#4A90D9', angry:'#E74C3C',
  fear:'#E67E22', disgust:'#27AE60', surprise:'#9B59B6', neutral:'#95A5A6'
};

// ── State ─────────────────────────────────────────────────────────────────────
let sessionActive = false;
let sessionId = null;
let sessionStartTime = null;
let frameCount = 0;
let snapshotCount = 0;
let durationTimer = null;
let liveChart = null;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const btnStart    = document.getElementById('btnStart');
const btnStop     = document.getElementById('btnStop');
const btnSnapshot = document.getElementById('btnSnapshot');
const sessionDot  = document.getElementById('sessionDot');
const sessionStatus = document.getElementById('sessionStatus');
const sessionInfo = document.getElementById('sessionInfo');

const faceCountBadge   = document.getElementById('faceCountBadge');
const faceCountEl      = document.getElementById('faceCount');
const dominantDisplay  = document.getElementById('dominantDisplay');
const dominantEmoji    = document.getElementById('dominantEmoji');
const dominantLabel    = document.getElementById('dominantLabel');
const dominantConfidence = document.getElementById('dominantConfidence');
const dominantGlow     = document.getElementById('dominantGlow');
const emotionBarsEl    = document.getElementById('emotionBars');
const stressAlert      = document.getElementById('stressAlert');
const videoWrapper     = document.getElementById('videoWrapper');
const recordingBadge   = document.getElementById('recordingBadge');
const multiFaceList    = document.getElementById('multiFaceList');

const statSessionId = document.getElementById('statSessionId');
const statDuration  = document.getElementById('statDuration');
const statFrames    = document.getElementById('statFrames');
const statSnapshots = document.getElementById('statSnapshots');

const snapshotCard     = document.getElementById('snapshotCard');
const snapshotImg      = document.getElementById('snapshotImg');
const snapshotDownload = document.getElementById('snapshotDownload');

const toastContainer   = document.getElementById('toastContainer');

// ── Theme ─────────────────────────────────────────────────────────────────────
const themeToggle = document.getElementById('themeToggle');
(function() {
  const saved = localStorage.getItem('theme') || 'dark';
  if (saved === 'light') { document.body.classList.add('light'); themeToggle.textContent = '☀️'; }
})();
themeToggle.addEventListener('click', () => {
  document.body.classList.toggle('light');
  const isLight = document.body.classList.contains('light');
  themeToggle.textContent = isLight ? '☀️' : '🌙';
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
});

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<span>${msg}</span>`;
  toastContainer.appendChild(t);
  setTimeout(() => { t.classList.add('toast-out'); setTimeout(() => t.remove(), 300); }, 3500);
}

// ── Build emotion bars ────────────────────────────────────────────────────────
function buildEmotionBars() {
  emotionBarsEl.innerHTML = EMOTIONS_LIST.map(e => `
    <div class="emotion-bar-row">
      <div class="emotion-bar-label">${EMOTION_EMOJIS[e]} ${e}</div>
      <div class="emotion-bar-track">
        <div class="emotion-bar-fill fill-${e}" id="bar-${e}" style="width:0%;"></div>
      </div>
      <div class="emotion-bar-pct" id="pct-${e}">0%</div>
    </div>`).join('');
}

function updateEmotionBars(emotions) {
  EMOTIONS_LIST.forEach(e => {
    const pct = (emotions[e] || 0).toFixed(1);
    const bar = document.getElementById(`bar-${e}`);
    const lbl = document.getElementById(`pct-${e}`);
    if (bar) bar.style.width = pct + '%';
    if (lbl) lbl.textContent = pct + '%';
  });
}

// ── Update dominant display ───────────────────────────────────────────────────
let lastDominant = null;
function updateDominant(dominant, emotions) {
  if (dominant === lastDominant) return;
  lastDominant = dominant;
  dominantEmoji.textContent = EMOTION_EMOJIS[dominant] || '😐';
  dominantLabel.textContent = dominant.charAt(0).toUpperCase() + dominant.slice(1);
  const conf = (emotions[dominant] || 0).toFixed(1);
  dominantConfidence.textContent = `Confidence: ${conf}%`;
  const color = EMOTION_COLORS_MAP[dominant] || '#888';
  dominantDisplay.style.borderColor = color + '55';
  dominantDisplay.style.background = color + '11';
  dominantGlow.style.background = color;
}

// ── Multi-face list ───────────────────────────────────────────────────────────
function updateMultiFace(allFaces) {
  if (!allFaces || !allFaces.length) {
    multiFaceList.textContent = 'No faces detected.';
    return;
  }
  multiFaceList.innerHTML = allFaces.map((face, i) => {
    const dom = face.dominant || 'neutral';
    const conf = (face.emotions && face.emotions[dom] || 0).toFixed(0);
    const color = EMOTION_COLORS_MAP[dom] || '#888';
    return `<div style="padding:8px 12px; margin-bottom:6px; border-radius:8px; border:1px solid ${color}33; background:${color}0d;">
      <strong style="color:${color}">Face ${i+1}:</strong>
      ${EMOTION_EMOJIS[dom]} ${dom.charAt(0).toUpperCase()+dom.slice(1)} — ${conf}% confidence
    </div>`;
  }).join('');
}

// ── Session controls ──────────────────────────────────────────────────────────
btnStart.addEventListener('click', async () => {
  try {
    const titleVal = document.getElementById('sessionTitleInput') ? document.getElementById('sessionTitleInput').value.trim() : '';
    const catVal = document.getElementById('sessionCategorySelect') ? document.getElementById('sessionCategorySelect').value : 'General';

    const res = await fetch('/api/start_session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: titleVal, category: catVal })
    });
    const data = await res.json();
    if (data.error) { showToast(data.error, 'error'); return; }
    sessionActive = true;
    sessionId = data.session_id;
    sessionStartTime = Date.now();
    frameCount = 0; snapshotCount = 0;
    statSessionId.textContent = '#' + sessionId;
    statFrames.textContent = '0';
    statSnapshots.textContent = '0';

    btnStart.disabled = true;
    btnStop.disabled = false;
    sessionDot.classList.add('recording');
    sessionStatus.textContent = 'Recording…';
    videoWrapper.classList.add('recording');
    recordingBadge.classList.add('visible');
    sessionInfo.textContent = `Session ${sessionId} (${catVal}) started. Recording emotion data.`;

    durationTimer = setInterval(() => {
      const sec = Math.floor((Date.now() - sessionStartTime) / 1000);
      const m = String(Math.floor(sec/60)).padStart(2,'0');
      const s = String(sec%60).padStart(2,'0');
      statDuration.textContent = `${m}:${s}`;
    }, 1000);

    showToast(`✅ Session ${sessionId} started`, 'success');
  } catch(e) { showToast('Failed to start session', 'error'); }
});

btnStop.addEventListener('click', async () => {
  try {
    const res = await fetch('/api/stop_session', { method: 'POST' });
    const data = await res.json();
    sessionActive = false;
    clearInterval(durationTimer);

    btnStart.disabled = false;
    btnStop.disabled = true;
    sessionDot.classList.remove('recording');
    videoWrapper.classList.remove('recording');
    recordingBadge.classList.remove('visible');
    sessionStatus.textContent = 'Session ended';

    const sum = data.summary || {};
    sessionInfo.innerHTML = `
      Session stopped. Dominant: <strong>${(sum.dominant||'N/A').charAt(0).toUpperCase()+(sum.dominant||'N/A').slice(1)}</strong>.
      ${sum.mood_text || ''} &nbsp;·&nbsp; <a href="/history" style="color:var(--accent-primary);">View History →</a> &nbsp;·&nbsp; <a href="/analytics" style="color:var(--accent-secondary);">Analytics →</a>`;

    showToast(`✅ Session saved! ${sum.mood_text || ''}`, 'success');
  } catch(e) { showToast('Failed to stop session', 'error'); }
});

// ── Snapshot ──────────────────────────────────────────────────────────────────
btnSnapshot.addEventListener('click', async () => {
  try {
    btnSnapshot.disabled = true;
    btnSnapshot.textContent = '⏳';
    const res = await fetch('/api/snapshot', { method: 'POST' });
    const data = await res.json();
    if (data.error) { showToast(data.error, 'error'); return; }

    snapshotCount++;
    statSnapshots.textContent = snapshotCount;
    snapshotImg.src = data.url + '?t=' + Date.now();
    snapshotDownload.href = data.url;
    snapshotDownload.download = data.filename;
    snapshotCard.style.display = 'block';
    showToast('📸 Snapshot saved!', 'success');
  } catch(e) {
    showToast('Failed to capture snapshot', 'error');
  } finally {
    btnSnapshot.disabled = false;
    btnSnapshot.textContent = '📸 Take Snapshot';
  }
});

// ── SocketIO ──────────────────────────────────────────────────────────────────
const socket = io();

socket.on('connect', () => {
  document.getElementById('connectionBadge').textContent = '⚡ Connected';
  document.getElementById('connectionBadge').className = 'badge badge-green';
});

socket.on('disconnect', () => {
  document.getElementById('connectionBadge').textContent = '✗ Disconnected';
  document.getElementById('connectionBadge').className = 'badge badge-red';
});

let lastStressTime = 0;
function playAlertChime() {
  try {
    const soundEnabled = localStorage.getItem('faceiq_sound_alerts') !== 'false';
    if (!soundEnabled) return;
    const now = Date.now();
    if (now - lastStressTime < 15000) return; // chime at most every 15s
    lastStressTime = now;
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(440, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.2);
    gain.gain.setValueAtTime(0.2, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch(e) {}
}

socket.on('emotion_update', (data) => {
  // Face count
  faceCountEl.textContent = data.face_count || 0;

  // Update emotion bars
  if (data.emotions) {
    updateEmotionBars(data.emotions);

    // Compute Positivity Index
    const pos = (data.emotions.happy || 0) + (data.emotions.surprise || 0) * 0.4;
    const posEl = document.getElementById('positivityVal');
    const posDesc = document.getElementById('positivityDesc');
    if (posEl) posEl.textContent = Math.min(100, Math.round(pos)) + '%';
    if (posDesc) {
      if (pos > 60) posDesc.textContent = 'High Positivity 😊';
      else if (pos > 30) posDesc.textContent = 'Pleasant & Upbeat 🙂';
      else if (data.emotions.neutral > 50) posDesc.textContent = 'Calm & Composed 😐';
      else posDesc.textContent = 'Tension Detected 😟';
    }
  }

  // Dominant
  if (data.dominant) updateDominant(data.dominant, data.emotions || {});

  // Multi-face
  updateMultiFace(data.all_faces || []);

  // Stress alert
  if (data.stress_alert) {
    stressAlert.classList.add('visible');
    playAlertChime();
  } else {
    stressAlert.classList.remove('visible');
  }

  // Live chart
  if (liveChart && data.emotions && data.timestamp) {
    updateTimelineChart(liveChart, data.timestamp, data.emotions);
  }

  // Stats
  if (sessionActive) {
    frameCount++;
    statFrames.textContent = frameCount;
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────
buildEmotionBars();
liveChart = initTimelineChart('timelineCanvas');

