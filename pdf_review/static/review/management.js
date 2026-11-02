import { AppDialog } from './dialogs.js';
import { appFetch } from './http.js';
import { SectionsWorkspace } from './sections_workspace.js';

let viewer = null;
let sectionsPanel = null;
export function registerManagement(context) {
  viewer = context;
  const query = new URLSearchParams(location.search);
  if (context.config.isOwner && query.get('sectionsPanel') === '1') openSections(context.config.documentId, null, query.get('section'));
}

export async function openSettings(documentId, opener) {
  const dialog = new AppDialog('Review settings', { opener });
  dialog.body.textContent = 'Loading…'; dialog.open();
  try {
    const response = await appFetch(`/documents/${documentId}/review-settings`);
    if (!response.ok) throw new Error('Review settings could not be loaded.');
    dialog.body.innerHTML = await response.text();
    const form = dialog.body.querySelector('form');
    form.querySelector('select').focus();
    form.querySelector('[data-dialog-cancel]').onclick = () => dialog.close();
    form.onsubmit = async event => {
      event.preventDefault(); dialog.setBusy(true);
      const error = form.querySelector('.dialog-error'); error.textContent = '';
      try {
        const saved = await appFetch(form.action, { method: 'POST', body: new FormData(form), headers: { Accept: 'application/json' } });
        const data = await saved.json();
        if (!saved.ok) throw new Error(data.error?.message || 'Settings could not be saved.');
        await viewer?.refresh();
        dialog.setBusy(false); dialog.close();
      } catch (failure) { error.textContent = failure.message; dialog.setBusy(false); }
    };
  } catch (error) { dialog.body.textContent = error.message; }
  return dialog;
}

export async function openSections(documentId, opener, selectedId = null) {
  if (sectionsPanel?.dialog.element.isConnected) { sectionsPanel.dialog.open(); return sectionsPanel; }
  if (!viewer) {
    // Sections are spatial tools: enter the current PDF rather than opening a modal.
    const response = await appFetch(`/documents/${documentId}/sections`);
    if (!response.ok) return;
    const data = await response.json();
    if (data.version_id) {
      location.assign(`/versions/${encodeURIComponent(data.version_id)}/view?sectionsPanel=1`);
      return;
    }
  }
  sectionsPanel = new SectionsWorkspace(documentId, { opener, viewer, selectedId });
  return sectionsPanel.open();
}

document.addEventListener('click', event => {
  const settings = event.target.closest('[data-review-settings]');
  const sections = event.target.closest('[data-sections]');
  if (!settings && !sections) return;
  event.preventDefault();
  document.querySelectorAll('.toolbar-menu[open]').forEach(menu => { menu.open = false; });
  if (settings) openSettings(settings.dataset.reviewSettings, settings);
  else openSections(sections.dataset.sections, sections);
});
document.documentElement.dataset.managementReady = 'true';
