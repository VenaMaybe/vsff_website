export class ReviewState {
  constructor() {
    this.anchors = [];
    this.threads = [];
    this.sectionThreads = [];
    this.currentReviewer = null;
    this.selectedThreadId = null;
    this.filter = "open";
  }

  setThreads(threads) {
    const oldTargetIds = new Set(this.threads.flatMap((thread) => thread.targets.map((target) => target.anchor.anchor_id)));
    const anchors = new Map(this.anchors.filter((anchor) => !oldTargetIds.has(anchor.anchor_id)).map((anchor) => [anchor.anchor_id, anchor]));
    for (const thread of threads) {
      for (const target of thread.targets) anchors.set(target.anchor.anchor_id, target.anchor);
    }
    this.anchors = [...anchors.values()];
    this.threads = threads;
    if (this.selectedThreadId && ![...threads,...this.sectionThreads].some((thread) => thread.thread_id === this.selectedThreadId)) {
      this.selectedThreadId = null;
    }
  }

  replaceThread(thread) {
    const index = this.threads.findIndex((item) => item.thread_id === thread.thread_id);
    const threads = [...this.threads];
    if (index >= 0) {
      threads.splice(index, 1, thread);
    } else {
      threads.push(thread);
    }
    this.setThreads(threads);
  }

  thread(threadId) {
    return [...this.threads,...this.sectionThreads].find((item) => item.thread_id === threadId) ?? null;
  }

  visibleThreads() {
    const text = this.filter === "all"
      ? this.threads
      : this.threads.filter((thread) => thread.status === "open");
    return [...text,...this.sectionThreads];
  }

  threadStates() {
    return this.threads.flatMap((thread) =>
      thread.targets.map((target) => ({
        anchorId: target.anchor.anchor_id,
        threadId: thread.thread_id,
        status: thread.status,
        color: thread.review_color,
      }))
    );
  }
}
