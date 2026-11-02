let sequence = 0;

// Native modal focus trapping/inertness, with one shared close/focus contract.
export class AppDialog {
  constructor(title, { size = 'medium', opener = document.activeElement } = {}) {
    this.opener = opener?.getClientRects().length ? opener : opener?.closest('.toolbar-menu')?.querySelector(':scope > summary') || opener;
    this.element = document.createElement('dialog');
    this.element.className = `app-dialog dialog-${size}`;
    const header = document.createElement('header');
    header.className = 'dialog-header';
    const heading = document.createElement('h2');
    heading.id = `app-dialog-title-${++sequence}`;
    heading.textContent = title;
    this.element.setAttribute('aria-labelledby', heading.id);
    const close = document.createElement('button');
    close.type = 'button'; close.textContent = '×'; close.setAttribute('aria-label', `Close ${title}`);
    close.addEventListener('click', () => this.close());
    header.append(heading, close);
    this.body = document.createElement('div'); this.body.className = 'dialog-body';
    this.element.append(header, this.body);
    this.element.addEventListener('cancel', event => { event.preventDefault(); this.close(); });
    this.element.addEventListener('close', () => {
      this.element.remove();
      if (this.opener?.isConnected) this.opener.focus({ preventScroll: true });
      this.onClose?.();
    });
  }
  open() {
    document.body.append(this.element); this.element.showModal();
    (this.body.querySelector('[autofocus], input, select, textarea, button') || this.element.querySelector('button')).focus();
    return this;
  }
  close() { if (!this.busy && this.element.open) this.element.close(); }
  setBusy(value) {
    this.busy = value; this.element.setAttribute('aria-busy', String(value));
    this.body.inert = value;
    if (value) {
      this.busyControls = [...this.element.querySelectorAll('button')].map(button => [button, button.disabled]);
      this.busyControls.forEach(([button]) => { button.disabled = true; });
    } else this.busyControls?.forEach(([button, disabled]) => { if (button.isConnected) button.disabled = disabled; });
  }
}

export function confirmAction(title, message, opener) {
  return new Promise(resolve => {
    const dialog = new AppDialog(title, { size: 'confirmation', opener });
    const text = document.createElement('p'); text.textContent = message;
    const actions = document.createElement('div'); actions.className = 'dialog-actions';
    const cancel = document.createElement('button'); cancel.textContent = 'Cancel'; cancel.autofocus = true;
    const confirm = document.createElement('button'); confirm.textContent = 'Delete';
    let accepted = false;
    cancel.onclick = () => dialog.close();
    confirm.onclick = () => { accepted = true; dialog.close(); };
    dialog.onClose = () => resolve(accepted);
    actions.append(cancel, confirm); dialog.body.append(text, actions); dialog.open();
  });
}
