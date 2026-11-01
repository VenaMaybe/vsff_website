export class SelectionCommentComposer {
  constructor(container, form, body, quote, cancelButton, onSubmit) {
    this.container = container;
    this.form = form;
    this.body = body;
    this.quote = quote;
    this.payload = null;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!this.payload) return;
      await onSubmit(this.payload, body.value);
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
    this.payload = null;
    this.body.value = "";
    this.container.hidden = true;
  }

  setBusy(busy) {
    for (const control of this.form.elements) {
      control.disabled = busy;
    }
  }
}
