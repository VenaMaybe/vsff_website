export class SelectionCommentComposer {
  constructor(container, form, body, quote, cancelButton, onSubmit) {
    this.container = container;
    this.form = form;
    this.body = body;
    this.quote = quote;
    this.payload = null;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!this.payload || this.busy) return;
      await onSubmit(this.payload, body.value);
    });
    body.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); form.requestSubmit(); }
    });
    cancelButton.addEventListener("click", () => this.close());
  }

  open(payload) {
    this.payload = payload;
    this.quote.textContent = payload.selection_text;
    this.container.hidden = false;
    this.body.value = "";
    this.body.focus();
  }

  close() {
    if (this.busy) return;
    this.payload = null;
    this.body.value = "";
    this.container.hidden = true;
  }

  setBusy(busy) {
    this.busy = busy;
    for (const control of this.form.elements) {
      control.disabled = busy;
    }
  }
}
