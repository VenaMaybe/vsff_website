export class ReviewPresence {
  constructor(versionId, container) {
    Object.assign(this, { versionId, container });
    this.page = null;
    this.timer = null;
    this.send = () => {};
  }
  render(event) {
    if (event?.schema_version !== 1 || event.version_id !== this.versionId ||
        !Array.isArray(event.reviewers)) return;
    const rows = event.reviewers.filter((user) => typeof user?.display_name === "string");
    document.getElementById("presence-count").textContent = rows.length;
    this.container.textContent = rows.length
      ? rows.map((user) => `${user.display_name}${Number.isInteger(user.page) ? ` · p. ${user.page}` : ""}`).join(", ")
      : "No named reviewers connected";
  }
  clear() { document.getElementById("presence-count").textContent = "0"; this.container.textContent = "Presence unavailable"; }
  watch(application, send) {
    this.send = send;
    this.page = application.pdfViewer.currentPageNumber;
    application.eventBus.on("pagechanging", ({ pageNumber }) => {
      if (pageNumber === this.page) return;
      this.page = pageNumber;
      if (this.timer) return;
      this.timer = window.setTimeout(() => {
        this.timer = null;
        this.sendCurrentPage();
      }, 350);
    });
    this.sendCurrentPage();
  }
  sendCurrentPage() {
    if (Number.isInteger(this.page) && this.page > 0) this.send(this.page);
  }
}
