let maxUploadMB = 25;
const form = document.querySelector('#translate-form');
const taskMode = document.querySelector('#task-mode');
let resultKind = 'translation';
const output = document.querySelector('#output');
const status = document.querySelector('#status');
const submit = document.querySelector('#submit');
const clearText = document.querySelector('#clear-text');
const spinner = document.querySelector('#translate-spinner');
const translateLabel = document.querySelector('#translate-label');
const translateArrow = document.querySelector('#translate-arrow');
function setTranslating(busy) {
  submit.disabled = busy;
  clearText.disabled = busy;
  taskMode.disabled = busy;
  submit.setAttribute('aria-busy', String(busy));
  spinner.hidden = !busy;
  translateArrow.hidden = busy;
  const transcribing = taskMode.value === 'transcribe';
  translateLabel.textContent = busy ? (transcribing ? 'Transcribing…' : 'Translating…') : (transcribing ? 'Transcribe' : 'Translate');
}
const copy = document.querySelector('#copy');
const download = document.querySelector('#download');
const downloadPDF = document.querySelector('#download-pdf');
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (submit.disabled) return;
  setTranslating(true);
  output.value = '';
  copy.disabled = download.disabled = downloadPDF.disabled = true;
  document.querySelector('#source-details').hidden = true;
  const file = document.querySelector('#file').files[0];
  const transcribing = taskMode.value === 'transcribe';
  status.textContent = transcribing ? 'Transcribing audio locally… This may take a few minutes.' : 'Translating… Audio and long documents may take a few minutes.';
  try {
    await loadUploadSettings();
    if (file && file.size > maxUploadMB * 1024 * 1024) { status.textContent = `Files must be smaller than ${maxUploadMB} MB.`; return; }
    if (document.querySelector('#source_language').value === 'auto') {
      translateLabel.textContent = 'Detecting…';
      status.textContent = 'Detecting the language locally… Review the result before continuing.';
      await detectSource(new FormData(form));
      return;
    }
    const response = await fetch(transcribing ? '/api/transcribe' : '/api/translate', { method: 'POST', body: new FormData(form) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Translation failed.');
    resultKind = transcribing ? 'transcript' : 'translation';
    output.value = transcribing ? data.transcript : data.translation;
    document.querySelector('#source').textContent = data.source || '';
    document.querySelector('#source-details').hidden = transcribing;
    status.textContent = transcribing ? 'Transcription complete. Review the transcript before saving.' : `Translated into ${data.language}.`;
    copy.disabled = download.disabled = downloadPDF.disabled = false;
  } catch (error) { status.textContent = error.message || 'Could not connect to the server.'; }
  finally { setTranslating(false); }
});
copy.addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(output.value); status.textContent = resultKind === 'transcript' ? 'Transcript copied.' : 'Translation copied.'; }
  catch { output.focus(); output.select(); status.textContent = 'Select and copy the text manually.'; }
});
download.addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([output.value], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = `glts-${resultKind}.txt`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

const settings = document.querySelector('#settings');
const darkMode = document.querySelector('#dark-mode');
try { darkMode.checked = localStorage.getItem('glts-theme') === 'dark'; } catch {}
function applyTheme() { document.documentElement.dataset.theme = darkMode.checked ? 'dark' : 'light'; }
applyTheme();
darkMode.addEventListener('change', () => {
  applyTheme();
  try { localStorage.setItem('glts-theme', darkMode.checked ? 'dark' : 'light'); } catch {}
});
const packStatus = document.querySelector('#pack-status');
const packList = document.querySelector('#pack-list');
const refreshPacks = document.querySelector('#refresh-packs');
const searchPacks = document.querySelector('#pack-search');
let packs = [];
let packBusy = false;
function renderPacks() {
  packList.replaceChildren();
  const query = searchPacks.value.trim().toLowerCase();
  const shown = packs.filter(p => `${p.source} ${p.target}`.toLowerCase().includes(query));
  for (const pack of shown) {
    const row = document.createElement('div'); row.className = 'pack-row';
    const label = document.createElement('span'); label.textContent = `${pack.source} → ${pack.target}`;
    const button = document.createElement('button'); button.type = 'button';
    button.textContent = pack.installed ? 'Installed' : 'Download';
    button.disabled = pack.installed || packBusy;
    button.addEventListener('click', () => requestPacks('/api/packs/install', { id: pack.id }, `Downloading ${pack.source} → ${pack.target}… Please wait.`));
    row.append(label, button); packList.append(row);
  }
  if (!shown.length) {
    const empty = document.createElement('p'); empty.className = 'hint';
    empty.textContent = packs.length ? 'No packs match your search.' : 'Refresh available packs while online to see languages you can download.';
    packList.append(empty);
  }
}
function updateLanguages(items) {
  for (const id of ['source_language', 'language']) {
    const select = document.getElementById(id);
    const previous = select.value;
    const choices = items.map(item => new Option(item.name, item.code));
    if (id === 'source_language') choices.unshift(new Option('Auto-detect (experimental)', 'auto'));
    if (id === 'source_language') choices.push(new Option('Sana’ani Arabic (Yemen)', 'ar-sanaa'));
    if (id === 'source_language' && previous && !choices.some(option => option.value === previous)) choices.push(new Option(select.selectedOptions[0].textContent, previous));
    select.replaceChildren(...choices);
    if (choices.some(option => option.value === previous)) select.value = previous;
  }
}
async function requestPacks(url, body, message) {
  if (packBusy) return;
  packBusy = true; refreshPacks.disabled = true; renderPacks(); packStatus.textContent = message;
  try {
    const response = await fetch(url, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not load language packs.');
    packs = data.packs; updateLanguages(data.languages);
    packStatus.textContent = url.endsWith('/install') ? 'Pack installed. It is ready for offline translation.' : 'Installed packs are ready for offline use.';
  } catch (error) { packStatus.textContent = error.message; }
  finally { packBusy = false; refreshPacks.disabled = false; renderPacks(); }
}
document.querySelector('#open-settings').addEventListener('click', () => {
  settings.showModal();
  checkLocalModels();
  if (!packBusy) requestPacks('/api/packs', undefined, 'Reading local packs…');
});
document.querySelector('#close-settings').addEventListener('click', () => settings.close());
refreshPacks.addEventListener('click', () => requestPacks('/api/packs/refresh', {}, 'Fetching available language packs…'));
searchPacks.addEventListener('input', renderPacks);

const limitInput = document.querySelector('#max-upload');
const settingsStatus = document.querySelector('#settings-status');
function applyUploadSettings(data) {
  maxUploadMB = data.max_upload_mb;
  document.querySelector('#compute-mode').value = data.compute_mode;
  document.querySelector('#cuda-status').textContent = data.cuda_available ? 'NVIDIA GPU detected. CUDA mode requires CUDA 12 and cuDNN 9 libraries.' : 'No CUDA GPU detected. CPU mode is available.';
  limitInput.value = maxUploadMB;
  document.querySelector('#upload-limit-label').textContent = maxUploadMB;
}
async function loadUploadSettings() {
  try {
    const response = await fetch('/api/settings');
    if (!response.ok) throw new Error('Could not read file-size settings.');
    applyUploadSettings(await response.json());
  } catch (error) { settingsStatus.textContent = error.message; }
}
loadUploadSettings();
document.querySelector('#save-upload-limit').addEventListener('click', async () => {
  if (!limitInput.reportValidity()) return;
  const button = document.querySelector('#save-upload-limit'); button.disabled = true;
  try {
    const response = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ max_upload_mb: Number(limitInput.value) }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    applyUploadSettings(data); settingsStatus.textContent = `File limit saved: ${maxUploadMB} MB.`;
  } catch (error) { settingsStatus.textContent = error.message; }
  finally { button.disabled = false; }
});

document.querySelector('#save-compute-mode').addEventListener('click', async () => {
  const button = document.querySelector('#save-compute-mode'); button.disabled = true;
  try {
    settingsStatus.textContent = 'Saving processing mode…';
    const response = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ compute_mode: document.querySelector('#compute-mode').value }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    applyUploadSettings(data); settingsStatus.textContent = `Processing mode saved: ${data.compute_mode.toUpperCase()}.`;
  } catch (error) { settingsStatus.textContent = error.message; }
  finally { button.disabled = false; }
});

const engine = document.querySelector('#engine');
const llmModel = document.querySelector('#llm-model');
function showEngine() { document.querySelector('#llm-options').hidden = engine.value !== 'ollama'; }
try {
  if (localStorage.getItem('glts-engine') === 'ollama') engine.value = 'ollama';
  const previousModel = localStorage.getItem('glts-llm');
  if (['qwen2.5:3b', 'qwen2.5:7b', 'qwen2.5:14b'].includes(previousModel)) llmModel.value = previousModel;
} catch {}
showEngine();
engine.addEventListener('change', () => { showEngine(); try { localStorage.setItem('glts-engine', engine.value); } catch {} });
llmModel.addEventListener('change', () => { try { localStorage.setItem('glts-llm', llmModel.value); } catch {} });
const modelStatus = document.querySelector('#local-model-status');
const downloadStatus = document.querySelector('#local-download-status');
const llmInstall = document.querySelector('#install-llm');
let modelPoll;
async function checkLocalModels() {
  clearTimeout(modelPoll);
  try {
    const response = await fetch('/api/local-models');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not check models.');
    const downloading = data.job.state === 'running';
    llmInstall.disabled = downloading || !data.ollama_connected;
    modelStatus.textContent = data.ollama_connected ? `Ollama connected. Installed language models: ${data.installed_models.join(', ') || 'none'}.` : 'Ollama is not running. Install/start Ollama, then click Check models.';
    downloadStatus.textContent = data.job.message;
    if (downloading) modelPoll = setTimeout(checkLocalModels, 3000);
  } catch (error) { modelStatus.textContent = error.message; }
}
async function installLocalModel(body) {
  llmInstall.disabled = true;
  downloadStatus.textContent = 'Starting model download…';
  try {
    const response = await fetch('/api/local-models/install', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not start download.');
    await checkLocalModels();
  } catch (error) {
    await checkLocalModels();
    downloadStatus.textContent = error.message;
  }
}
llmInstall.addEventListener('click', () => installLocalModel({ kind: 'llm', model: document.querySelector('#download-llm').value }));
document.querySelector('#refresh-models').addEventListener('click', checkLocalModels);

const sourceSelect = document.querySelector('#source_language');
const detectionReview = document.querySelector('#detection-review');
const detectedSource = document.querySelector('#detected-source');
function showAutoOptions() {
  document.querySelector('#auto-options').hidden = sourceSelect.value !== 'auto';
  detectionReview.hidden = true;
}
sourceSelect.addEventListener('change', showAutoOptions);
showAutoOptions();
function clearDetection() { detectionReview.hidden = true; }
document.querySelector('#text').addEventListener('input', clearDetection);
document.querySelector('#file').addEventListener('change', clearDetection);
document.querySelector('#remove-file').addEventListener('click', clearDetection);
async function detectSource(body) {
  const originalText = document.querySelector('#text').value;
  const originalFile = document.querySelector('#file').files[0];
  detectionReview.hidden = true;
  const response = await fetch('/api/detect', { method: 'POST', body });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Source detection failed.');
  if (document.querySelector('#text').value !== originalText || document.querySelector('#file').files[0] !== originalFile || sourceSelect.value !== 'auto') throw new Error('The input changed during detection. Detect again or choose the source manually.');
  const options = Array.from(sourceSelect.options).filter(option => option.value !== 'auto').map(option => new Option(option.textContent, option.value));
  if (!options.some(option => option.value === data.language)) options.push(new Option(data.name, data.language));
  detectedSource.replaceChildren(...options);
  detectedSource.value = data.dialect || data.language;
  document.querySelector('#detection-warning').textContent = `Detected language: ${data.name}. ${data.warning}`;
  document.querySelector('#detection-preview').textContent = data.preview;
  detectionReview.hidden = false;
  status.textContent = 'Review the detected source, then click Confirm source language. Processing has not started.';
}
document.querySelector('#confirm-detection').addEventListener('click', () => {
  if (detectionReview.hidden || submit.disabled) return;
  if (!Array.from(sourceSelect.options).some(option => option.value === detectedSource.value)) sourceSelect.add(new Option(detectedSource.selectedOptions[0].textContent, detectedSource.value));
  sourceSelect.value = detectedSource.value;
  showAutoOptions();
  status.textContent = 'Source confirmed. Click the main action button to continue, or choose another source manually.';
});

clearText.addEventListener('click', () => {
  if (submit.disabled) return;
  const input = document.querySelector('#text');
  const file = document.querySelector('#file');
  input.value = '';
  file.value = '';
  file.dispatchEvent(new Event('change', { bubbles: true }));
  output.value = '';
  copy.disabled = download.disabled = downloadPDF.disabled = true;
  document.querySelector('#source').textContent = '';
  document.querySelector('#source-details').hidden = true;
  document.querySelector('#detection-preview').textContent = '';
  document.querySelector('#detection-warning').textContent = '';
  clearDetection();
  status.textContent = taskMode.value === 'transcribe' ? 'Cleared. Choose an audio file to transcribe.' : 'Cleared. Paste new text or choose a file to translate.';
  input.focus();
});

downloadPDF.addEventListener('click', async () => {
  if (!output.value.trim()) return;
  const text = output.value;
  const kind = resultKind;
  downloadPDF.disabled = true;
  status.textContent = 'Preparing PDF…';
  try {
    const response = await fetch('/api/export/pdf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, kind }) });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || 'Could not save the PDF.');
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a'); link.href = url; link.download = `glts-${kind}.pdf`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    if (output.value === text && !submit.disabled) status.textContent = 'PDF download started.';
  } catch (error) {
    if (output.value === text && !submit.disabled) status.textContent = error.message;
  } finally { downloadPDF.disabled = submit.disabled || !output.value.trim(); }
});

taskMode.addEventListener('change', () => {
  const transcribing = taskMode.value === 'transcribe';
  document.querySelector('#translation-controls').hidden = transcribing;
  document.querySelector('#result-title').textContent = transcribing ? 'Your transcript' : 'Your translation';
  output.setAttribute('aria-label', transcribing ? 'Transcript' : 'Translated text');
  output.placeholder = transcribing ? 'Your original-language transcript will appear here.' : 'A new language. The same meaning.';
  document.querySelector('#task-hint').textContent = transcribing ? 'Upload audio to get its original-language transcript. No translation pack or Ollama is required.' : 'Translate text, documents, or audio into another language.';
  document.querySelector('#dialect-note').textContent = transcribing ? 'Choose the spoken language. Audio uses standard Whisper; Sana’ani is treated as Arabic. Auto-detect lets you review the source first.' : 'Audio uses standard Whisper. Select the local language model for Sana’ani text or transcript translation. Accuracy needs review.';
  output.value = '';
  document.querySelector('#source').textContent = '';
  document.querySelector('#source-details').hidden = true;
  copy.disabled = download.disabled = downloadPDF.disabled = true;
  clearDetection();
  setTranslating(false);
  status.textContent = transcribing ? 'Upload audio, choose the spoken language, then click Transcribe.' : 'Your translated text will appear here.';
});
