/* OmniVoice TTS — Frontend Logic */
'use strict';

// ── Slider definitions ──────────────────────────────────────────────────────
const ADV_SLIDERS = [
  { id: 'steps',    label: 'Steps',          min: 4,   max: 64,        step: 1,    def: 32 },
  { id: 'guidance', label: 'Guidance Scale', min: 0.0, max: 10.0,      step: 0.5,  def: 2.0 },
  { id: 'speed',    label: 'Speed',          min: 0.5, max: 2.0,       step: 0.05, def: 1.0 },
  { id: 'tshift',   label: 't-shift',        min: 0.0, max: 1.0,       step: 0.05, def: 0.1 },
  { id: 'seed',     label: 'Seed (0=random)',min: 0,   max: 2147483647,step: 1,    def: 0   },
  { id: 'duration', label: 'Duration s (0=auto)', min: 0.0, max: 60.0, step: 0.5,  def: 0.0 },
];

const EXPERT_SLIDERS = [
  { id: 'postemp',  label: 'Position Temp', min: 0.0, max: 20.0, step: 0.5, def: 5.0 },
  { id: 'clstemp',  label: 'Class Temp',    min: 0.0, max: 5.0,  step: 0.1, def: 0.0 },
  { id: 'layerpen', label: 'Layer Penalty', min: 0.0, max: 20.0, step: 0.5, def: 5.0 },
];

// Build slider grid into a container element, prefix ids
function buildSliders(container, defs, prefix) {
  container.innerHTML = '';
  for (const s of defs) {
    const uid = `${prefix}-${s.id}`;
    const row = document.createElement('div');
    row.className = 'slider-row';
    row.innerHTML = `
      <label for="${uid}">${s.label} <span class="slider-val" id="${uid}-val">${s.def}</span></label>
      <input type="range" id="${uid}" min="${s.min}" max="${s.max}" step="${s.step}" value="${s.def}">
    `;
    container.appendChild(row);
    const input = row.querySelector('input');
    const valEl = row.querySelector('.slider-val');
    input.addEventListener('input', () => { valEl.textContent = parseFloat(input.value); });
  }
}

function getSliderVal(prefix, id) {
  return parseFloat(document.getElementById(`${prefix}-${id}`).value);
}

// ── Init sliders ────────────────────────────────────────────────────────────
['clone', 'design', 'lf', 'vc2'].forEach(p => {
  buildSliders(document.getElementById(`${p}-adv-sliders`),    ADV_SLIDERS,    p);
  buildSliders(document.getElementById(`${p}-expert-sliders`), EXPERT_SLIDERS, p);
});

// ── Mode switching ──────────────────────────────────────────────────────────
document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`panel-${btn.dataset.panel}`).classList.add('active');
  });
});

// ── Tab switching ───────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const bar = btn.closest('.tab-bar');
    bar.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const panel = btn.closest('.panel') || btn.closest('.adv-body') || document.body;
    panel.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.getElementById(btn.dataset.tab).classList.add('active');
  });
});

// ── Drop zones ──────────────────────────────────────────────────────────────
function setupDropZone(zoneId, inputId, nameId, onFile) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  const name  = document.getElementById(nameId);

  function setFile(file) {
    zone.classList.add('has-file');
    name.textContent = file.name;
    if (onFile) onFile(file);
  }

  input.addEventListener('change', () => { if (input.files[0]) setFile(input.files[0]); });

  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    zone.classList.add('drop-accept');
    setTimeout(() => zone.classList.remove('drop-accept'), 300);
    const f = e.dataTransfer.files[0];
    if (f) {
      const dt = new DataTransfer();
      dt.items.add(f);
      input.files = dt.files;
      setFile(f);
    }
  });
}

// txt file → fill textarea
function onTxtFile(file) {
  const reader = new FileReader();
  reader.onload = e => { document.getElementById('lf-text').value = e.target.result; };
  reader.readAsText(file);
}

setupDropZone('clone-drop',    'clone-ref-file', 'clone-ref-name');
setupDropZone('lf-drop',       'lf-ref-file',    'lf-ref-name');
setupDropZone('lf-txt-drop',   'lf-txt-file',    'lf-txt-name',   onTxtFile);
setupDropZone('vc2-drop',      'vc2-src-file',   'vc2-src-name');
setupDropZone('vc2-ref-drop',  'vc2-ref-file',   'vc2-ref-name');

// ── Sample scripts ──────────────────────────────────────────────────────────
let SCRIPTS = {};

async function loadScripts() {
  try {
    const res = await fetch('/api/sample_scripts');
    SCRIPTS = await res.json();
    const keys = Object.keys(SCRIPTS);
    ['clone', 'lf', 'vc2'].forEach(p => {
      const dd = document.getElementById(`${p}-script-dd`);
      if (!dd) return;
      dd.innerHTML = '';
      keys.forEach(k => {
        const opt = document.createElement('option');
        opt.value = k;
        opt.textContent = k;
        dd.appendChild(opt);
      });
      dd.addEventListener('change', () => {
        document.getElementById(`${p}-script-box`).textContent = SCRIPTS[dd.value] || '';
      });
      // init
      document.getElementById(`${p}-script-box`).textContent = SCRIPTS[keys[0]] || '';
    });
  } catch (e) {
    console.warn('loadScripts failed', e);
  }
}

loadScripts();

// ── Mic recorder ────────────────────────────────────────────────────────────
function setupMic(prefix) {
  let mediaRec = null;
  let chunks   = [];
  let timerInt = null;
  let elapsed  = 0;
  let micBlob  = null;

  const recBtn   = document.getElementById(`${prefix}-rec-btn`);
  const stopBtn  = document.getElementById(`${prefix}-rec-stop`);
  const dot      = document.getElementById(`${prefix}-rec-dot`);
  const timer    = document.getElementById(`${prefix}-rec-timer`);
  const audio    = document.getElementById(`${prefix}-mic-audio`);

  if (!recBtn) return;

  function fmtTime(s) { return `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`; }

  recBtn.addEventListener('click', async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRec = new MediaRecorder(stream);
      chunks = [];
      mediaRec.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
      mediaRec.onstop = () => {
        clearInterval(timerInt);
        dot.classList.remove('recording');
        recBtn.style.display = '';
        stopBtn.style.display = 'none';
        const blob = new Blob(chunks, { type: mediaRec.mimeType || 'audio/webm' });
        micBlob = blob;
        const url = URL.createObjectURL(blob);
        audio.src = url;
        audio.style.display = '';
        // expose blob for form submission
        window[`${prefix}_mic_blob`] = blob;
        window[`${prefix}_mic_mime`] = blob.type;
      };
      mediaRec.start();
      elapsed = 0;
      timer.textContent = fmtTime(0);
      timerInt = setInterval(() => { elapsed++; timer.textContent = fmtTime(elapsed); }, 1000);
      dot.classList.add('recording');
      recBtn.style.display = 'none';
      stopBtn.style.display = '';
    } catch (e) {
      alert('ไม่สามารถเข้าถึงไมค์ได้: ' + e.message);
    }
  });

  stopBtn.addEventListener('click', () => {
    if (mediaRec && mediaRec.state !== 'inactive') mediaRec.stop();
    mediaRec.stream.getTracks().forEach(t => t.stop());
  });
}

['clone', 'lf', 'vc2'].forEach(setupMic);

// ── GPU status ──────────────────────────────────────────────────────────────
async function refreshStatus() {
  try {
    const res  = await fetch('/api/status');
    const data = await res.json();
    document.getElementById('gpu-badge').textContent = data.gpu_info || '';
  } catch (e) {}
}

refreshStatus();

// ── Unload model ────────────────────────────────────────────────────────────
document.getElementById('unload-btn').addEventListener('click', async () => {
  const btn = document.getElementById('unload-btn');
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const res = await fetch('/api/unload', { method: 'POST' });
    const d   = await res.json();
    document.getElementById('gpu-badge').textContent = d.gpu_info || '';
  } catch (e) {}
  btn.disabled = false;
  btn.textContent = '⏏ Unload Model';
});

// ── SSE helpers ─────────────────────────────────────────────────────────────
function showProgress(prefix, frac, desc) {
  const wrap = document.getElementById(`${prefix}-progress`);
  const bar  = document.getElementById(`${prefix}-prog-bar`);
  const desc_ = document.getElementById(`${prefix}-prog-desc`);
  wrap.classList.add('visible');
  bar.value = frac;
  if (desc_) desc_.textContent = desc || '';
}

function hideProgress(prefix) {
  document.getElementById(`${prefix}-progress`).classList.remove('visible');
}

function showOutput(prefix, fileUrl, status) {
  const wrap   = document.getElementById(`${prefix}-output`);
  const audio  = document.getElementById(`${prefix}-audio`);
  const stat   = document.getElementById(`${prefix}-status`);
  const dl     = document.getElementById(`${prefix}-dl`);
  wrap.classList.add('visible');
  audio.src  = fileUrl;
  stat.textContent = status || '';
  dl.href    = fileUrl;
  dl.download = fileUrl.split('/').pop();
  refreshStatus();
}

function setGenBtnState(prefix, busy) {
  const btn = document.getElementById(`${prefix}-gen-btn`);
  btn.disabled  = busy;
  btn.textContent = busy
    ? '⏳ กำลังสร้าง…'
    : (prefix === 'vc2' ? '▶ แปลงเสียง' : '▶ สร้างเสียง');
}

// Build FormData from element id map
function buildForm(fields) {
  const fd = new FormData();
  for (const [key, val] of Object.entries(fields)) {
    if (val === null || val === undefined) continue;
    if (val instanceof File || val instanceof Blob) {
      fd.append(key, val);
    } else {
      fd.append(key, String(val));
    }
  }
  return fd;
}

function getModelSettings() {
  return {
    model_choice:   document.getElementById('model-choice').value,
    dtype_choice:   document.getElementById('dtype-choice').value,
    attn_choice:    document.getElementById('attn-choice').value,
    whisper_enable: 'false',
  };
}

function getAdvSliders(prefix) {
  return {
    steps:         getSliderVal(prefix, 'steps'),
    guidance:      getSliderVal(prefix, 'guidance'),
    speed:         getSliderVal(prefix, 'speed'),
    t_shift:       getSliderVal(prefix, 'tshift'),
    seed:          getSliderVal(prefix, 'seed'),
    duration:      getSliderVal(prefix, 'duration'),
    pos_temp:      getSliderVal(prefix, 'postemp'),
    cls_temp:      getSliderVal(prefix, 'clstemp'),
    layer_penalty: getSliderVal(prefix, 'layerpen'),
  };
}

async function streamGenerate(endpoint, fd, prefix, onDone) {
  setGenBtnState(prefix, true);
  showProgress(prefix, 0, 'กำลังเริ่มต้น…');

  try {
    const res = await fetch(endpoint, { method: 'POST', body: fd });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const reader = res.body.getReader();
    const dec    = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();  // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        try {
          const obj = JSON.parse(line.slice(5).trim());
          if (obj.type === 'progress') {
            showProgress(prefix, obj.frac, obj.desc);
          } else if (obj.type === 'done') {
            hideProgress(prefix);
            if (onDone) onDone(obj.result);
          } else if (obj.type === 'error') {
            hideProgress(prefix);
            alert('เกิดข้อผิดพลาด:\n' + obj.message);
          }
        } catch (e) {}
      }
    }
  } catch (e) {
    hideProgress(prefix);
    alert('เกิดข้อผิดพลาด: ' + e.message);
  } finally {
    setGenBtnState(prefix, false);
  }
}

// ── Voice Clone ─────────────────────────────────────────────────────────────
function getRefAudio(prefix) {
  // mic blob takes priority
  const blob = window[`${prefix}_mic_blob`];
  if (blob) return blob;
  const input = document.getElementById(`${prefix}-ref-file`);
  return input && input.files[0] ? input.files[0] : null;
}

document.getElementById('clone-asr-btn').addEventListener('click', async () => {
  const ref = getRefAudio('clone');
  if (!ref) { alert('กรุณาอัปโหลดหรืออัดเสียง reference ก่อน'); return; }
  const fd = new FormData();
  fd.append('audio', ref);
  try {
    const res = await fetch('/api/transcribe', { method: 'POST', body: fd });
    const d = await res.json();
    document.getElementById('clone-ref-txt').value = d.text || '';
  } catch (e) { alert('Transcribe ล้มเหลว: ' + e.message); }
});

document.getElementById('clone-gen-btn').addEventListener('click', async () => {
  const text = document.getElementById('clone-text').value;
  const ref  = getRefAudio('clone');
  if (!text.trim()) { alert('กรุณาใส่ข้อความ'); return; }
  if (!ref)          { alert('กรุณาอัปโหลดหรืออัดเสียง reference'); return; }

  const fd = buildForm({
    ...getModelSettings(),
    ...getAdvSliders('clone'),
    text,
    ref_text:  document.getElementById('clone-ref-txt').value,
    instruct:  document.getElementById('clone-instruct').value,
    ref_audio: ref,
  });

  await streamGenerate('/api/generate/clone', fd, 'clone', r => {
    if (r && r.file) showOutput('clone', r.file, r.status);
  });
});

// ── Voice Design ─────────────────────────────────────────────────────────────
document.getElementById('design-gen-btn').addEventListener('click', async () => {
  const text = document.getElementById('design-text').value;
  const inst = document.getElementById('design-inst').value;
  if (!text.trim()) { alert('กรุณาใส่ข้อความ'); return; }
  if (!inst.trim()) { alert('กรุณาระบุ voice description'); return; }

  const fd = buildForm({
    ...getModelSettings(),
    ...getAdvSliders('design'),
    text,
    instruct: inst,
  });

  await streamGenerate('/api/generate/design', fd, 'design', r => {
    if (r && r.file) showOutput('design', r.file, r.status);
  });
});

// ── Longform ─────────────────────────────────────────────────────────────────
document.getElementById('lf-gen-btn').addEventListener('click', async () => {
  const text = document.getElementById('lf-text').value;
  if (!text.trim()) { alert('กรุณาใส่ข้อความ'); return; }

  const ref = getRefAudio('lf');

  const fd = buildForm({
    ...getModelSettings(),
    ...getAdvSliders('lf'),
    text,
    ref_text:        document.getElementById('lf-ref-txt').value,
    instruct:        document.getElementById('lf-inst').value,
    chunk_size:      document.getElementById('lf-chunk').value,
    silence_ms:      document.getElementById('lf-sil').value,
    use_consistency: document.getElementById('lf-consistency').checked ? 'true' : 'false',
    ref_audio: ref,
  });

  await streamGenerate('/api/generate/longform', fd, 'lf', r => {
    if (r && r.file) showOutput('lf', r.file, r.status);
  });
});

// ── Voice Convert ────────────────────────────────────────────────────────────
document.getElementById('vc2-transcribe-btn').addEventListener('click', async () => {
  const src = document.getElementById('vc2-src-file').files[0];
  if (!src) { alert('กรุณาอัปโหลดไฟล์เสียงต้นทางก่อน'); return; }
  document.getElementById('vc2-transcribe-status').textContent = 'กำลัง transcribe…';
  const fd = new FormData();
  fd.append('audio', src);
  try {
    const res = await fetch('/api/transcribe', { method: 'POST', body: fd });
    const d = await res.json();
    document.getElementById('vc2-src-text').value = d.text || '';
    document.getElementById('vc2-transcribe-status').textContent = d.status || '';
  } catch (e) {
    document.getElementById('vc2-transcribe-status').textContent = 'เกิดข้อผิดพลาด: ' + e.message;
  }
});

document.getElementById('vc2-gen-btn').addEventListener('click', async () => {
  const srcFile = document.getElementById('vc2-src-file').files[0];
  const ref     = getRefAudio('vc2');
  if (!srcFile) { alert('กรุณาอัปโหลดไฟล์เสียงต้นทาง'); return; }
  if (!ref)     { alert('กรุณาอัปโหลดหรืออัดเสียง reference'); return; }

  const fd = buildForm({
    ...getModelSettings(),
    ...getAdvSliders('vc2'),
    src_text: document.getElementById('vc2-src-text').value,
    ref_text: document.getElementById('vc2-ref-txt').value,
    src_audio: srcFile,
    ref_audio: ref,
  });

  await streamGenerate('/api/generate/convert', fd, 'vc2', r => {
    if (!r) return;
    if (r.file) showOutput('vc2', r.file, r.status);
    if (r.transcript) {
      document.getElementById('vc2-text-out').style.display = '';
      document.getElementById('vc2-text-out-box').textContent = r.transcript;
    }
  });
});
