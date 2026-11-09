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
    if (this.selectedThreadId && ![...threads,...this.sectionThreads].some((thread) => thread.thread_id === this.selectedThreadId && this.hasVisibleComments(thread))) {
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
    return [...text,...this.sectionThreads]
      .filter((thread) => this.hasVisibleComments(thread))
      .map((thread) => ({...thread, comments:thread.comments.filter((comment,index) => !comment.is_deleted || index === 0)}));
  }

  hasVisibleComments(thread) {
    // Keep the empty section prompt where a reader can add their first response.
    return (thread.section && !thread.response_id) || thread.comments.some((comment) => !comment.is_deleted);
  }

  visibleAnchors() {
    const hidden = new Set(this.threads.filter((thread) => !this.hasVisibleComments(thread))
      .flatMap((thread) => thread.targets.map((target) => target.anchor.anchor_id)));
    return this.anchors.filter((anchor) => !hidden.has(anchor.anchor_id));
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
