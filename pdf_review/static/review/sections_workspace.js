import { AppDialog, confirmAction } from './dialogs.js';
import { jsonRequest } from './thread_api.js';
import { SectionsPanel } from './sections_panel.js';

function node(tag, text, className = '') {
  const element = document.createElement(tag); element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function button(text, action) { const b = node('button', text); b.type = 'button'; b.onclick = action; return b; }
function boundary(placement, kind) {
  const y = placement[`${kind}_y`], box = placement[`${kind}_view_box`];
  const level = y === null ? (kind === 'start' ? 'top' : 'bottom') : `${Math.round((box[3] - y) / (box[3] - box[1]) * 100)}%`;
  return `p. ${placement[`${kind}_page`]} · ${level}`;
}

export class SectionsWorkspace {
  constructor(documentId, { opener, viewer, selectedId }) {
    Object.assign(this, { documentId, viewer, selectedId });
    this.versionId = viewer?.config.versionId || null;
    this.drafts = new Map();
    this.dialog = new SectionsPanel(opener, visible => {
      this.viewer?.sectionViewer.setManagementVisible(visible, this.selectedId);
      if (!visible && this.viewer?.sectionViewer.onEditorReturn) {
        this.viewer.sectionViewer.onEditorReturn = null;
        this.viewer.sectionViewer.finishEditing();
      }
    });
  }
  async open() {
    this.dialog.body.textContent = 'Loading…'; this.dialog.open();
    await this.load(); return this;
  }
  async load() {
    try {
      const query = this.versionId ? `?version=${encodeURIComponent(this.versionId)}` : '';
      const data = await jsonRequest(`/documents/${this.documentId}/sections${query}`);
      this.sections = data.sections; this.versions = data.versions; this.versionId = data.version_id;
      if (this.selectedId !== 'new' && !this.sections.some(s => s.section_id === this.selectedId)) this.selectedId = this.sections[0]?.section_id || null;
      this.render();
    } catch (error) { this.dialog.body.textContent = error.message; }
  }
  render() {
    const toolbar = node('div', undefined, 'sections-toolbar');
    const label = node('label', 'PDF version '), version = node('select'); version.setAttribute('aria-label', 'Section placement version');
    for (const v of this.versions) { const option = node('option', v.version_label || v.original_filename); option.value = v.version_id; version.append(option); }
    version.value = this.versionId || ''; version.onchange = () => {
      if (this.viewer) {
        location.assign(`/versions/${encodeURIComponent(version.value)}/view?sectionsPanel=1&section=${encodeURIComponent(this.selectedId || '')}`);
      } else { this.versionId = version.value; this.load(); }
    };
    label.append(version); toolbar.append(label);
    const layout = node('div', undefined, 'sections-workspace');
    this.master = node('nav', undefined, 'sections-master'); this.master.setAttribute('aria-label', 'Sections');
    this.list = node('div', undefined, 'section-master-list');
    this.master.append(this.list, button('+ Add section', () => {
      this.selectedId = 'new'; this.drafts.set('new', { name: '', prompt: '' }); this.renderList(); this.renderDetail(); this.name.focus();
    }), button('Import outline…', () => this.importOutline()));
    this.detail = node('div', undefined, 'section-detail');
    this.error = node('p', '', 'dialog-error'); this.error.setAttribute('role', 'alert');
    layout.append(this.master, this.detail); this.dialog.body.replaceChildren(toolbar, layout, this.error);
    this.renderList(); this.renderDetail();
  }
  renderList() {
    this.viewer?.sectionViewer.setManagementVisible(this.dialog.element.isConnected, this.selectedId);
    this.list.replaceChildren();
    const items = [...this.sections];
    if (this.selectedId === 'new') items.push({ section_id: 'new', name: 'New section' });
    for (const [index, section] of items.entries()) {
      const item = button(`${index + 1}  ${section.name}`, () => { this.selectedId = section.section_id; this.renderList(); this.renderDetail(); this.name.focus(); });
      item.className = 'section-master-item'; item.dataset.sectionId = section.section_id;
      item.setAttribute('aria-current', String(this.selectedId === section.section_id));
      item.append(node('small', section.placement ? 'Mapped' : 'Unmapped'));
      item.onkeydown = event => {
        if (!['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault(); const buttons = [...this.list.children], i = buttons.indexOf(item);
        const target = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : Math.max(0, Math.min(buttons.length - 1, i + (event.key === 'ArrowDown' ? 1 : -1)));
        this.selectedId = buttons[target].dataset.sectionId; this.renderList(); this.renderDetail(); this.list.children[target].focus();
      };
      this.list.append(item);
    }
  }
  renderDetail() {
    this.detail.replaceChildren();
    const section = this.sections.find(s => s.section_id === this.selectedId);
    if (!section && this.selectedId !== 'new') { this.detail.append(node('p', 'Add a section to define document structure.')); return; }
    const draft = this.drafts.get(this.selectedId) || { name: section.name, prompt: section.prompt };
    this.drafts.set(this.selectedId, draft);
    const form = node('form'); form.id = 'section-detail-form';
    const nameLabel = node('label', 'Name'), promptLabel = node('label', 'Optional author prompt');
    this.name = node('input'); this.name.name = 'name'; this.name.maxLength = 200; this.name.required = true; this.name.value = draft.name;
    const prompt = node('textarea'); prompt.name = 'prompt'; prompt.maxLength = 2000; prompt.value = draft.prompt;
    this.name.oninput = () => { draft.name = this.name.value; }; prompt.oninput = () => { draft.prompt = prompt.value; };
    nameLabel.append(this.name); promptLabel.append(prompt); form.append(nameLabel, promptLabel);
    const summary = node('div', undefined, 'placement-summary');
    summary.append(node('h3', 'Placement'), node('p', section?.placement ? `Start ${boundary(section.placement, 'start')} · End ${boundary(section.placement, 'end')}` : 'Unmapped in this version'));
    if (section?.previous_placements.length) {
      const previous = node('details'); previous.append(node('summary', 'Previous versions'));
      for (const p of section.previous_placements) previous.append(node('p', `${p.version_label || 'Earlier version'} · pages ${p.start_page}–${p.end_page}`));
      summary.append(previous);
    }
    const edit = button('Edit boundaries in document', () => this.editBoundaries()); edit.disabled = !this.versionId;
    summary.append(edit); form.append(summary);
    const controls = node('div', undefined, 'section-order-controls');
    for (const [offset, title] of [[-1, 'Move up'], [1, 'Move down']]) {
      const move = button(title, () => this.reorder(offset)); move.disabled = !section || !this.sections[this.sections.indexOf(section) + offset]; controls.append(move);
    }
    form.append(controls);
    const actions = node('div', undefined, 'dialog-actions');
    if (section) actions.append(button('Delete', event => this.remove(section, event.currentTarget)));
    const save = node('button', 'Save'); save.type = 'submit'; actions.append(save); form.append(actions);
    form.onsubmit = event => { event.preventDefault(); this.save(); }; this.detail.append(form);
  }
  async operation(work) {
    if (this.dialog.busy) return false;
    this.error.textContent = ''; this.dialog.setBusy(true);
    try { await work(); return true; }
    catch (error) { this.error.textContent = error.message; return false; }
    finally { this.dialog.setBusy(false); }
  }
  async save() {
    if (!this.detail.querySelector('form').reportValidity()) return false;
    return this.operation(async () => {
      const id = this.selectedId, draft = this.drafts.get(id);
      if (id === 'new') this.selectedId = (await jsonRequest(`/api/documents/${this.documentId}/sections`, { method: 'POST', body: JSON.stringify(draft) })).section_id;
      else await jsonRequest(`/api/sections/${id}`, { method: 'PATCH', body: JSON.stringify(draft) });
      this.drafts.delete(id); await this.load(); await this.viewer?.refresh();
    });
  }
  async remove(section, opener) {
    if (!await confirmAction('Delete section', `Delete “${section.name}”? Saved placements and feedback will be retained.`, opener)) return;
    await this.operation(async () => { await jsonRequest(`/api/sections/${section.section_id}`, { method: 'PATCH', body: JSON.stringify({ archive: true }) }); this.drafts.delete(section.section_id); await this.load(); await this.viewer?.refresh(); });
  }
  async reorder(offset) {
    const index = this.sections.findIndex(s => s.section_id === this.selectedId), other = this.sections[index + offset];
    if (!other) return;
    await this.operation(async () => {
      const order = [...this.sections]; [order[index], order[index + offset]] = [order[index + offset], order[index]];
      for (const [position, section] of order.entries()) if (section.position !== position) await jsonRequest(`/api/sections/${section.section_id}`, { method: 'PATCH', body: JSON.stringify({ position }) });
      await this.load(); await this.viewer?.refresh();
    });
  }
  async editBoundaries() {
    // Save an explicitly edited/new definition before handing its stable ID to the viewer.
    if (!await this.save()) return;
    this.handoff('boundaries');
  }
  importOutline() { if (this.versionId) this.handoff('outline'); }
  handoff(mode) {
    const restore = async selectedId => {
      if (typeof selectedId === 'string') this.selectedId = selectedId;
      this.dialog.body.textContent = 'Loading sections…';
      this.dialog.open(); await this.load(); this.list?.querySelector('[aria-current=true]')?.focus();
    };
    if (this.viewer?.config.versionId === this.versionId) {
      if (mode === 'outline') this.viewer.sectionViewer.previewOutline().catch(error => this.viewer.sectionViewer.status(error.message,'error')).finally(restore);
      else this.viewer.sectionViewer.beginEditing(this.selectedId, restore);
      return;
    }
    this.dialog.close();
    // A document page has no PDF canvas. Host the existing authorized viewer in
    // a temporary workspace, preserving the outer document URL and scroll state.
    const preview = new AppDialog(mode === 'outline' ? 'Import PDF outline' : 'Edit section boundaries', { size: 'workspace', opener: this.dialog.opener });
    preview.element.classList.add('section-preview-dialog');
    const frame = node('iframe'); frame.title = 'PDF section editor';
    frame.src = `/versions/${this.versionId}/view?management=${mode}&section=${encodeURIComponent(this.selectedId || '')}`;
    preview.body.append(frame);
    const receive = event => {
      if (event.origin !== location.origin || event.source !== frame.contentWindow || event.data?.type !== 'pdf-review:management-return') return;
      if (typeof event.data.sectionId === 'string') this.selectedId = event.data.sectionId;
      preview.close();
    };
    window.addEventListener('message', receive);
    preview.onClose = () => { window.removeEventListener('message', receive); restore(); };
    preview.open();
  }
}
