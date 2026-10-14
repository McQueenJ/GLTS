const form = document.querySelector('#translate-form');
const output = document.querySelector('#output');
const status = document.querySelector('#status');
const submit = document.querySelector('#submit');
const copy = document.querySelector('#copy');
const download = document.querySelector('#download');
form.addEventListener('submit', async event => {
  event.preventDefault();
  output.value = '';
  copy.disabled = download.disabled = true;
  document.querySelector('#source-details').hidden = true;
  const file = document.querySelector('#file').files[0];
  if (file && file.size > 25 * 1024 * 1024) { status.textContent = 'Files must be smaller than 25 MB.'; return; }
  submit.disabled = true;
  status.textContent = 'Translating… Audio and long documents may take a few minutes.';
  try {
    const response = await fetch('/api/translate', { method: 'POST', body: new FormData(form) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Translation failed.');
    output.value = data.translation;
    document.querySelector('#source').textContent = data.source;
    document.querySelector('#source-details').hidden = false;
    status.textContent = `Translated into ${data.language}.`;
    copy.disabled = download.disabled = false;
  } catch (error) { status.textContent = error.message || 'Could not connect to the server.'; }
  finally { submit.disabled = false; }
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
