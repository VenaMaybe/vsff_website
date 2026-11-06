import { AppDialog } from './dialogs.js';
import { appFetch } from './http.js';

let currentDialog;
document.querySelector('[data-share-document]')?.addEventListener('click', async event => {
  event.preventDefault();
  if (currentDialog?.element.isConnected) return;
  const opener = event.currentTarget;
  const dialog = new AppDialog('Share document', {opener});
  currentDialog = dialog;
  dialog.element.classList.add('share-dialog');
  dialog.body.textContent = 'Loading sharing options…';
  const controller = new AbortController();
  dialog.onClose = () => controller.abort();
  dialog.open();
  try {
    const url = new URL(opener.href);
    url.searchParams.set('share', '1');
    const response = await appFetch(url, {signal: controller.signal});
    if (!response.ok || response.redirected) throw new Error('Sharing options could not be loaded. Refresh the page and check your access.');
    const html = await response.text();
    if (!dialog.element.isConnected) return;
    dialog.body.innerHTML = html;
    dialog.body.querySelector('select, input:not([type=hidden])')?.focus({preventScroll: true});
    dialog.body.addEventListener('submit', async submit => {
      const form = submit.target.closest('[data-share-form]');
      if (!form) return;
      submit.preventDefault();
      if (dialog.busy) return;
      const error = dialog.body.querySelector('[data-share-error]');
      const result = dialog.body.querySelector('[data-share-result]');
      error.hidden = true;
      result.hidden = true;
      dialog.setBusy(true);
      try {
        const saved = await appFetch(form.getAttribute('action'), {method: 'POST', body: new FormData(form), headers: {Accept: 'application/json'}});
        const data = await saved.json().catch(() => null);
        if (!saved.ok || saved.redirected || !data) throw new Error(data?.error?.message || 'Sharing could not be completed. Refresh the page and check your access.');
        result.replaceChildren();
        const message = document.createElement('p');
        message.textContent = data.status === 'pending'
          ? `Invitation ready for ${data.email}. Copy the link and send it to them; no email has been sent automatically.`
          : data.message || `Access is available for ${data.email}. Existing document roles are preserved.`;
        result.append(message);
        if (data.invitation_link) {
          const label = document.createElement('label');
          const caption = document.createElement('span'); caption.textContent = 'Invitation link';
          const input = document.createElement('input'); input.readOnly = true; input.value = data.invitation_link;
          label.append(caption, input);
          const copy = document.createElement('button'); copy.type = 'button'; copy.textContent = 'Copy invitation link';
          const status = document.createElement('p'); status.className = 'subtle'; status.setAttribute('role', 'status');
          copy.addEventListener('click', async () => {
            try { await navigator.clipboard.writeText(input.value); status.textContent = 'Link copied.'; }
            catch { input.focus(); input.select(); status.textContent = 'Copy the selected link.'; }
          });
          result.append(label, copy, status);
        }
        result.hidden = false;
        result.scrollIntoView({block: 'nearest'});
      } catch (failure) {
        error.textContent = failure.message;
        error.hidden = false;
      } finally { dialog.setBusy(false); }
    });
  } catch (failure) {
    if (failure.name !== 'AbortError' && dialog.element.isConnected) dialog.body.textContent = failure.message;
  }
});
