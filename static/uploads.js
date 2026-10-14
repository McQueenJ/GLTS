(() => {
  const zone = document.querySelector('#drop-zone');
  const input = document.querySelector('#file');
  const message = document.querySelector('#upload-status');
  const remove = document.querySelector('#remove-file');
  const translate = document.querySelector('#submit');
  const allowed = input.accept.split(',').map(extension => extension.toLowerCase());
  let dragDepth = 0;
  function resetHighlight() {
    dragDepth = 0;
    zone.classList.remove('drag-over');
  }
  function showSelection() {
    const file = input.files[0];
    message.textContent = file ? `Selected: ${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)` : '';
    remove.hidden = !file;
  }
  function isFileDrag(event) { return Array.from(event.dataTransfer?.types || []).includes('Files'); }
  // Prevent dropped files outside the upload area from navigating away from GLTS.
  document.addEventListener('dragover', event => {
    if (isFileDrag(event)) event.preventDefault();
  });
  document.addEventListener('drop', event => {
    if (!isFileDrag(event)) return;
    event.preventDefault();
    resetHighlight();
    if (!zone.contains(event.target)) message.textContent = 'Drop your file inside the upload area.';
  });
  zone.addEventListener('dragenter', event => {
    if (!isFileDrag(event)) return;
    event.preventDefault();
    dragDepth += 1;
    if (!translate.disabled) zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) resetHighlight();
  });
  zone.addEventListener('dragover', event => {
    if (!isFileDrag(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = translate.disabled ? 'none' : 'copy';
  });
  zone.addEventListener('drop', event => {
    if (!isFileDrag(event)) return;
    event.preventDefault();
    resetHighlight();
    if (translate.disabled) { message.textContent = 'Wait for the current translation to finish before adding a file.'; return; }
    const files = Array.from(event.dataTransfer.files);
    if (files.length !== 1) { message.textContent = 'Please drop one file at a time.'; return; }
    const file = files[0];
    const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!allowed.includes(extension)) { message.textContent = 'This file type is not supported. Choose one of the formats listed above.'; return; }
    const limit = Number(document.querySelector('#upload-limit-label').textContent);
    if (file.size > limit * 1024 * 1024) { message.textContent = `Files must be smaller than ${limit} MB. You can change the limit in Settings.`; return; }
    try {
      const selection = new DataTransfer();
      selection.items.add(file);
      input.files = selection.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    } catch {
      message.textContent = 'Your browser could not accept the drop. Use Choose File instead.';
    }
  });
  input.addEventListener('change', showSelection);
  remove.addEventListener('click', () => {
    if (translate.disabled) { message.textContent = 'Wait for the current translation to finish before removing the file.'; return; }
    input.value = '';
    showSelection();
  });
})();
