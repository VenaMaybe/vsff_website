// A non-modal inspector: the PDF and review rail remain interactive.
export class SectionsPanel {
  constructor(opener, onVisibility) {
    this.opener = opener?.getClientRects().length ? opener : opener?.closest('.toolbar-menu')?.querySelector('summary');
    this.onVisibility = onVisibility;
    this.element = document.createElement('section');
    this.element.className = 'sections-panel';
    this.element.setAttribute('role', 'region');
    this.element.setAttribute('aria-labelledby', 'sections-panel-title');
    const header = document.createElement('header'); header.className = 'dialog-header';
    const title = document.createElement('h2'); title.id = 'sections-panel-title'; title.textContent = 'Sections';
    const close = document.createElement('button'); close.type = 'button'; close.textContent = '×'; close.setAttribute('aria-label', 'Close Sections');
    close.onclick = () => this.close(); header.append(title, close);
    this.body = document.createElement('div'); this.body.className = 'sections-panel-body';
    this.element.append(header, this.body);
    this.element.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); this.close(); }
    });
  }
  open() {
    if (!this.element.isConnected) document.body.append(this.element);
    document.querySelector('.viewer-workspace')?.classList.add('sections-panel-open');
    this.onVisibility?.(true);
    this.element.querySelector('button').focus({ preventScroll: true });
  }
  close() {
    if (this.busy) return;
    this.element.remove();
    document.querySelector('.viewer-workspace')?.classList.remove('sections-panel-open');
    this.onVisibility?.(false);
    if (this.opener?.isConnected) this.opener.focus({ preventScroll: true });
  }
  setBusy(value) {
    this.busy = value; this.element.setAttribute('aria-busy', String(value)); this.body.inert = value;
    this.element.querySelector('.dialog-header button').disabled = value;
  }
}
