let maxUploadMB = 25;
const form = document.querySelector('#translate-form');
const output = document.querySelector('#output');
const status = document.querySelector('#status');
const submit = document.querySelector('#submit');
const spinner = document.querySelector('#translate-spinner');
const translateLabel = document.querySelector('#translate-label');
const translateArrow = document.querySelector('#translate-arrow');
function setTranslating(busy) {
  submit.disabled = busy;
  submit.setAttribute('aria-busy', String(busy));
  spinner.hidden = !busy;
  translateArrow.hidden = busy;
  translateLabel.textContent = busy ? 'Translating…' : 'Translate';
}
const copy = document.querySelector('#copy');
const download = document.querySelector('#download');
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (submit.disabled) return;
  setTranslating(true);
  output.value = '';
  copy.disabled = download.disabled = true;
  document.querySelector('#source-details').hidden = true;
  const file = document.querySelector('#file').files[0];
  status.textContent = 'Translating… Audio and long documents may take a few minutes.';
  try {
    await loadUploadSettings();
    if (file && file.size > maxUploadMB * 1024 * 1024) { status.textContent = `Files must be smaller than ${maxUploadMB} MB.`; return; }
    const response = await fetch('/api/translate', { method: 'POST', body: new FormData(form) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Translation failed.');
    output.value = data.translation;
    document.querySelector('#source').textContent = data.source;
    document.querySelector('#source-details').hidden = false;
    status.textContent = `Translated into ${data.language}.`;
    copy.disabled = download.disabled = false;
  } catch (error) { status.textContent = error.message || 'Could not connect to the server.'; }
  finally { setTranslating(false); }
});
copy.addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(output.value); status.textContent = 'Translation copied.'; }
  catch { output.focus(); output.select(); status.textContent = 'Select and copy the translation manually.'; }
});
download.addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([output.value], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = 'glts-translation.txt'; link.click();
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
    select.replaceChildren(...items.map(item => new Option(item.name, item.code)));
    if (items.some(item => item.code === previous)) select.value = previous;
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
