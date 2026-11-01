import { fetchMigration, fetchTargetHistory, migrationAction } from "./migration_api.js";
import { RefreshCoordinator } from "./realtime.js";

function node(tag, text, className = "") {
  const result = document.createElement(tag);
  result.textContent = text;
  result.className = className;
  return result;
}

export class MigrationSidebar {
  constructor(url, capture, afterMutation, canMutate = true) {
    Object.assign(this, { url, capture, afterMutation, canMutate });
    this.run = null;
    this.intent = null;
    this.selection = null;
    this.busy = false;
    this.status = document.getElementById("migration-status");
    this.carry = document.getElementById("migration-carry");
    this.skip = document.getElementById("migration-skip");
    this.accept = document.getElementById("migration-accept");
    this.complete = document.getElementById("migration-complete");
    this.filter = document.getElementById("migration-filter");
    this.refresh = new RefreshCoordinator(() => fetchMigration(url), (run) => {
      this.run = run;
      this.render();
    }, (error) => { this.status.textContent = `Sync problem: ${error.message}`; });
    this.filter.addEventListener("change", () => this.render());
    document.getElementById("migration-refresh").addEventListener("click", () => this.refresh.request());
    this.carry.addEventListener("pointerdown", () => this.selectionChanged(this.capture()));
    this.carry.addEventListener("click", () => this.act(this.intent?.targetId ? "reanchor" : "carry"));
    this.skip.addEventListener("click", () => {
      const note = window.prompt("Optional reason for not carrying this discussion:", "");
      if (note !== null) this.act("skip", { note });
    });
    this.accept.addEventListener("click", () => this.act("accept"));
    this.complete.addEventListener("click", () => this.act("complete"));
    this.refresh.request();
  }

  selectionChanged(selection) {
    this.selection = selection;
    document.getElementById("migration-selection").textContent = selection
      ? `Target selection: ${selection.selection_text}`
      : "Select corresponding text in this PDF.";
    this.updateControls();
  }

  selectedItem() { return this.run?.items.find((item) => item.item_id === this.intent?.itemId); }
  stale(item) {
    return item && (item.revision_number !== this.intent.revision || item.current_target_id !== this.intent.targetId);
  }
  updateControls() {
    const item = this.selectedItem();
    const active = this.canMutate && !this.busy && this.run?.status === "open" && item && !this.stale(item) && item.state !== "skipped";
    this.carry.textContent = item?.current_target_id ? "Re-anchor selected thread here" : "Carry thread here";
    this.carry.disabled = !active || !this.selection || Boolean(item?.destination_is_origin);
    this.skip.disabled = !active || item.state !== "pending" || Boolean(item.current_target_id);
    this.accept.hidden = !(active && item.state === "pending" && item.current_target_id);
    this.complete.disabled = !this.canMutate || this.busy || this.run?.status !== "open" || this.run.counts.pending !== 0;
  }

  render() {
    if (!this.run) return;
    const counts = this.run.counts;
    document.getElementById("migration-counts").textContent = `${counts.pending} pending · ${counts.carried} carried · ${counts.skipped} skipped`;
    this.status.textContent = this.run.status === "completed"
      ? `Completed by ${this.run.completed_by.display_name} · ${this.run.completed_at}`
      : "Open run. All includes resolved discussions. Select a thread before mapping it.";
    const list = document.getElementById("migration-items");
    list.replaceChildren();
    for (const item of this.run.items.filter((item) => this.filter.value === "all" || item.thread.status === "open")) {
      const button = node("button", `${item.state.toUpperCase()} · ${item.thread.comments[0]?.author.display_name ?? "Discussion"} · ${item.source_target.anchor.selection_text}`, "migration-item");
      button.type = "button";
      button.dataset.itemId = item.item_id;
      button.dataset.threadId = item.thread_id;
      button.setAttribute("aria-pressed", String(item.item_id === this.intent?.itemId));
      button.addEventListener("click", () => {
        this.intent = { itemId: item.item_id, revision: item.revision_number, targetId: item.current_target_id };
        this.selectionChanged(null);
        this.render();
      });
      list.append(button);
    }
    const preview = document.getElementById("migration-preview");
    preview.replaceChildren();
    const item = this.selectedItem();
    if (item) {
      const anchor = item.source_target.anchor;
      preview.append(node("h3", `Source: ${this.run.source_label} · page ${anchor.segments[0].page_number}`),
                     node("blockquote", anchor.selection_text), node("p", `Discussion is ${item.thread.status}.`));
      const source = node("a", "Go to source");
      source.href = `/versions/${encodeURIComponent(this.run.source_version_id)}/view?thread=${encodeURIComponent(item.thread_id)}`;
      source.target = "_blank";
      source.rel = "noopener";
      preview.append(source);
      for (const comment of item.thread.comments) {
        preview.append(node("p", `${comment.author.display_name}: ${comment.is_deleted ? "This comment was deleted." : comment.body}`));
      }
      if (item.decision_by) preview.append(node("p", `${item.state} by ${item.decision_by.display_name} · ${item.decided_at}${item.skip_note ? ` · ${item.skip_note}` : ""}`));
      if (item.destination_is_origin) preview.append(node("p", "The original version's target is permanent and cannot be re-anchored."));
      if (this.stale(item)) preview.append(node("p", "Mapping changed elsewhere. Select this source thread again to review the latest target before saving."));
      const history = node("details", "");
      history.append(node("summary", "Target history / diagnostics"));
      history.addEventListener("toggle", async () => {
        if (!history.open || history.querySelector("pre")) return;
        try {
          const targets = await fetchTargetHistory(item.thread_id);
          for (const target of targets) {
            history.append(node("p", `${target.version_label} · ${target.role} · ${target.is_effective ? "effective" : "superseded"} · ${target.created_at}`));
          }
          history.append(node("pre", JSON.stringify(targets, null, 2)));
        } catch (error) { history.append(node("p", error.message)); }
      });
      preview.append(history);
    }
    this.updateControls();
  }

  async act(action, extra = {}) {
    if (!this.canMutate || this.busy || (action !== "complete" && !this.intent)) return;
    const payload = action === "complete" ? {} : {
      expected_revision: this.intent.revision,
      ...(action === "skip" ? extra : { expected_target_id: this.intent.targetId }),
      ...(["carry", "reanchor"].includes(action) ? { anchor: this.selection } : {}),
    };
    this.busy = true;
    this.updateControls();
    try {
      const suffix = action === "complete" ? "/complete" : `/items/${encodeURIComponent(this.intent.itemId)}/${action}`;
      const run = await migrationAction(this.url + suffix, payload);
      this.refresh.invalidate();
      this.run = run;
      const item = this.selectedItem();
      if (item) this.intent = { itemId: item.item_id, revision: item.revision_number, targetId: item.current_target_id };
      this.selectionChanged(null);
      this.render();
      this.status.textContent = action === "complete" ? "Run completed." : `Decision saved: ${action}.`;
      this.afterMutation();
    } catch (error) {
      await this.refresh.request();
      this.status.textContent = error.message;
    } finally {
      this.busy = false;
      this.updateControls();
    }
  }
}
