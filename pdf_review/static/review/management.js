import { AppDialog } from './dialogs.js';
import { LeftCard, registerLeftCard } from './left_card.js';
import { appFetch } from './http.js';
import { SectionsWorkspace } from './sections_workspace.js';

let viewer = null;
let sectionsPanel = null;
let settingsPanel = null;
export function registerManagement(context) {
  viewer = context;
  if(context.config.isOwner){
    registerLeftCard('settings',()=>openSettings(context.config.documentId,null));
    registerLeftCard('sections',async()=>(await openSections(context.config.documentId,null)).dialog);
  }
  context.sectionViewer.onActivateSection = (id, kind) => { context.deselectThread?.(); return openSections(context.config.documentId, null, id, kind); };
  const query = new URLSearchParams(location.search);
  if (context.config.isOwner && query.get('settingsPanel') === '1') openSettings(context.config.documentId, null);
  if (context.config.isOwner && (query.get('sectionsPanel') === '1' || query.get('sections') === 'edit')) openSections(context.config.documentId, null, query.get('section'));
}

export async function openSettings(documentId, opener) {
  if (settingsPanel?.element.isConnected) { settingsPanel.open(); return settingsPanel; }
  if (!viewer && await enterViewer(documentId, 'settingsPanel')) return;
  const dialog = viewer ? new LeftCard('Settings', { opener, viewer, className: 'settings-panel', stateKey:'settings' }) : new AppDialog('Settings', { opener });
  settingsPanel = dialog;
  dialog.body.textContent = 'Loading…'; if (dialog.open() === false) return;
  try {
    const response = await appFetch(`/documents/${documentId}/review-settings`);
    if (!response.ok) throw new Error('Settings could not be loaded.');
    dialog.body.innerHTML = await response.text();
    dialog.contentReady?.();
    const form = dialog.body.querySelector('form');
    if (!dialog.element.isConnected) return dialog;
    form.querySelector('select').focus({ preventScroll: true });
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

export async function openSections(documentId, opener, selectedId = null, boundaryKind = null) {
  if (sectionsPanel?.dialog.element.isConnected) { if (selectedId) sectionsPanel.select(selectedId, true, boundaryKind); else sectionsPanel.dialog.open(); return sectionsPanel; }
  if (!viewer && await enterViewer(documentId, 'sectionsPanel')) return;
  sectionsPanel ||= new SectionsWorkspace(documentId, { opener, viewer, selectedId });
  if(selectedId)sectionsPanel.selectedId=selectedId;
  await sectionsPanel.open();
  if (boundaryKind) sectionsPanel.select(selectedId, true, boundaryKind);
  return sectionsPanel;
}

async function enterViewer(documentId, panel) {
  const response = await appFetch(`/documents/${documentId}/sections`);
  if (!response.ok) throw new Error('Document could not be loaded.');
  const data = await response.json();
  if (!data.version_id) return false;
  location.assign(`/versions/${encodeURIComponent(data.version_id)}/view?${panel}=1`);
  return true;
}

document.addEventListener('click', event => {
  if (event.target.closest('[data-left-card]')) return;
  const settings = event.target.closest('[data-review-settings]');
  const sections = event.target.closest('[data-sections]');
  if (!settings && !sections) return;
  event.preventDefault();
  document.querySelectorAll('.toolbar-menu[open]').forEach(menu => { menu.open = false; });
  if (settings) openSettings(settings.dataset.reviewSettings, settings);
  else openSections(sections.dataset.sections, sections);
});
document.documentElement.dataset.managementReady = 'true';
