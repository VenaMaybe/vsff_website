// Serial canonical reads. Local HTTP results invalidate older in-flight reads.
export class RefreshCoordinator {
  constructor(fetchState, applyState, onError, onSuccess = () => {}) {
    Object.assign(this, { fetchState, applyState, onError, onSuccess });
    this.running = null;
    this.dirty = false;
    this.generation = 0;
  }
  invalidate() {
    this.generation += 1;
    if (this.running) this.dirty = true;
  }
  request() {
    this.dirty = true;
    if (!this.running) this.running = this.drain().finally(() => { this.running = null; });
    return this.running;
  }
  async drain() {
    while (this.dirty) {
      this.dirty = false;
      const generation = this.generation;
      try {
        const state = await this.fetchState();
        if (generation === this.generation) {
          this.applyState(state);
          this.onSuccess();
        }
      } catch (error) {
        this.onError(error); // Retain existing state on failed reads.
      }
    }
  }
}

export class ReviewRealtime {
  constructor(versionId, refresh, presence, status, onMigrationChanged = () => {}, onVersionDeleted = () => window.location.reload()) {
    Object.assign(this, { versionId, refresh, presence, status });
    this.joined = false;
    if (typeof window.io !== "function") {
      this.setStatus("Offline — collaboration updates unavailable");
      return;
    }
    this.socket = window.io({ autoConnect: false });
    this.socket.on("connect", () => {
      this.setStatus("Connecting…");
      this.socket.timeout(5000).emit("review.join", { version_id: versionId }, (error, result) => {
        if (error || !result?.ok || !this.socket.connected) {
          this.setStatus("Offline — could not join this version");
          return;
        }
        this.joined = true;
        this.presence.sendCurrentPage();
        this.refresh.request();
      });
    });
    this.socket.on("review.changed", (event) => {
      if (event?.schema_version === 1 && event.version_id === versionId &&
          typeof event.thread_id === "string" && typeof event.kind === "string") this.refresh.request();
    });
    this.socket.on('review.version_deleted',event=>{
      if(event?.schema_version===1&&event.version_id===versionId){this.joined=false;this.socket.disconnect();onVersionDeleted();}
    });
    this.socket.on("review.presence", (event) => this.presence.render(event));
    this.socket.on('review.invalidated',event=>{if(event?.schema_version===1 && event.version_id===versionId)this.refresh.request();});
    this.socket.on("migration.changed", (event) => {
      if (event?.schema_version === 1 && event.version_id === versionId) onMigrationChanged(event);
    });
    this.socket.on("disconnect", () => {
      this.joined = false;
      this.presence.clear();
      this.setStatus("Reconnecting… updates may be delayed");
    });
    this.socket.on("connect_error", () => {
      this.joined = false;
      this.presence.clear();
      this.setStatus("Offline — updates resume after reconnection");
    });
    window.addEventListener("pagehide", () => this.socket.disconnect());
    window.addEventListener("pageshow", (event) => {
      if (event.persisted) this.socket.connect();
    });
    this.socket.connect();
  }
  setStatus(message) {
    this.status.textContent = message;
    const menu = document.querySelector(".collaboration-menu");
    if (menu) {
      menu.dataset.connection = message === "Live" ? "live" : "offline";
      menu.querySelector("summary").title = message;
    }
  }
  synced() { if (this.joined) this.setStatus("Live"); }
  syncFailed() { this.setStatus("Sync problem — visible comments retained; retrying"); }
}
