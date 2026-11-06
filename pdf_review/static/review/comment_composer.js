// Input capability, not the chosen comment style or a narrow desktop window.
export function usesViewportComposer() {
  return matchMedia('(pointer: coarse)').matches;
}

export class SelectionCommentComposer {
  constructor(container, form, body, quote, cancelButton, onSubmit) {
    this.container = container;
    this.form = form;
    this.body = body;
    this.quote = quote;
    this.payload = null;
    this.home = document.createComment("selection composer home");
    container.before(this.home);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!this.payload || this.busy) return;
      await onSubmit(this.payload, body.value);
    });
    body.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); form.requestSubmit(); }
    });
    body.addEventListener("pointerdown", (event) => {
      if (event.pointerType !== 'touch' || !event.isPrimary ||
          !this.container.classList.contains('viewport-composer') ||
          document.activeElement === body) return;
      // Safari's default focus starts a native reveal-scroll animation that
      // competes with our visual-viewport docking during keyboard opening.
      // Focus inside this user gesture to open the keyboard without that scroll.
      event.preventDefault();
      body.focus({ preventScroll: true });
    });
    cancelButton.addEventListener("click", () => this.close());
  }

  open(payload) {
    this.payload = payload;
    this.quote.textContent = payload.selection_text;
    this.setViewportDocked(usesViewportComposer());
    this.container.hidden = false;
    this.body.value = "";
    this.position?.();
    this.focusForOpen();
  }

  focusForOpen() {
    // Safari can show its native form-navigation bar on programmatic focus
    // even without opening the keyboard. Apply the touch-device policy on
    // reopening too; a narrow mouse-driven window retains ordinary focus.
    if (!usesViewportComposer()) {
      this.body.focus({ preventScroll: true });
    }
  }

  setViewportDocked(docked) {
    if (this.container.classList.contains('viewport-composer') === docked) return;
    this.container.classList.toggle('viewport-composer', docked);
    // A keyboard-adjusted viewport overlay must not inherit PDF workspace
    // clipping or participate in the document's scroll extent calculations.
    if (docked) document.body.append(this.container);
    else this.home.after(this.container);
  }

  close() {
    if (this.busy) return;
    this.payload = null;
    this.body.value = "";
    this.container.hidden = true;
    this.setViewportDocked(false);
  }

  setBusy(busy) {
    this.busy = busy;
    for (const control of this.form.elements) {
      control.disabled = busy;
    }
  }
}
