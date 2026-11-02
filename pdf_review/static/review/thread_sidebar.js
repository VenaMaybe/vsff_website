const editForms = new Map();
const replyForms = new Map();

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function shortDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function pageLabel(thread) {
  const segments = thread.targets[0]?.anchor?.segments ?? [];
  if (!segments.length) return "Target unavailable";
  const first = segments[0].page_number;
  const last = segments.at(-1).page_number;
  return first === last ? `Page ${first}` : `Pages ${first}-${last}`;
}

function stopCardClick(event) {
  event.stopPropagation();
}

function inlineEdit(comment, actions) {
  if (editForms.has(comment.comment_id)) return editForms.get(comment.comment_id);
  // Hold the revision originally opened, even as canonical comments refresh.
  comment = { ...comment };
  const form = element("form", "inline-edit-form");
  const input = element("textarea");
  input.maxLength = 10000;
  input.required = true;
  input.value = comment.body;
  const controls = element("div", "composer-actions");
  const cancel = element("button", "quiet-control", "Cancel");
  cancel.type = "button";
  const save = element("button", "", "Save");
  save.type = "submit";
  controls.append(cancel, save);
  form.append(input, controls);
  form.addEventListener("click", stopCardClick);
  editForms.set(comment.comment_id, form);
  cancel.addEventListener("click", () => {
    editForms.delete(comment.comment_id);
    form.remove();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    save.disabled = true;
    try {
      const result = await actions.edit(comment, input.value);
      if (result === true) {
        editForms.delete(comment.comment_id);
        form.remove();
      } else if (result?.error?.code === "comment_conflict") {
        form.querySelector(".edit-conflict")?.remove();
        const conflict = element("div", "edit-conflict");
        conflict.append(element("p", "", result.error.message));
        const acknowledge = element("button", "quiet-control", "Use latest revision for next save");
        acknowledge.type = "button";
        save.disabled = true;
        acknowledge.addEventListener("click", () => {
          const latest = actions.currentComment(comment.comment_id);
          if (!latest || latest.is_deleted) return;
          comment.current_revision = latest.current_revision;
          conflict.remove();
          save.disabled = false;
        });
        conflict.append(acknowledge);
        form.append(conflict);
      }
    } finally {
      save.disabled = Boolean(form.querySelector(".edit-conflict"));
    }
  });
  return form;
}

function commentNode(comment, actions) {
  const node = element("div", "thread-comment");
  const meta = element("div", "thread-comment-meta");
  meta.append(
    element("strong", "", comment.author.display_name),
    element(
      "span",
      "",
      `${shortDate(comment.created_at)}${comment.edited_at ? " (edited)" : ""}`
    )
  );
  const body = element(
    "p",
    `thread-comment-body${comment.is_deleted ? " deleted" : ""}`,
    comment.is_deleted ? "This comment was deleted." : comment.body
  );
  node.append(meta, body);
  if (actions.canEdit(comment) && editForms.has(comment.comment_id)) node.append(editForms.get(comment.comment_id));
  if (!comment.is_deleted) {
    const controls = element("div", "comment-actions");
    const edit = element("button", "text-action", "Edit");
    edit.type = "button";
    edit.addEventListener("click", (event) => {
      stopCardClick(event);
      node.append(inlineEdit(comment, actions));
    });
    const remove = element("button", "text-action danger", "Delete");
    remove.type = "button";
    remove.addEventListener("click", async (event) => {
      stopCardClick(event);
      if (window.confirm("Delete this comment? Its history and replies will be preserved.")) {
        await actions.remove(comment);
      }
    });
    if (actions.canEdit(comment)) controls.append(edit);
    if (actions.canEdit(comment)) controls.append(remove);
    node.append(controls);
  }
  return node;
}

function threadCard(thread, selectedThreadId, actions) {
  const card = element(
    "article",
    `thread-card${thread.thread_id === selectedThreadId ? " active" : ""}${
      thread.status === "resolved" ? " resolved" : ""
    }`
  );
  card.dataset.threadId = thread.thread_id;
  card.tabIndex = 0;
  const header = element("div", "thread-card-header");
  header.append(element("span", "thread-card-location", pageLabel(thread)));
  const headerActions = element("div", "comment-actions");
  if (thread.status === "resolved") {
    headerActions.append(element("span", "thread-status-badge", "Resolved"));
  }
  if (thread.thread_id === selectedThreadId) {
    const close = element("button", "text-action", "Close");
    close.type = "button";
    close.addEventListener("click", (event) => {
      stopCardClick(event);
      actions.deselect();
    });
    headerActions.append(close);
  }
  header.append(headerActions);
  const history = thread.status_history ?? [];
  const statusHistory = element("div", "thread-status-history");
  const actionLabel = (change) => `${change.action === "resolved" ? "Resolved" : "Reopened"} by ${change.actor.display_name} · ${shortDate(change.created_at)}`;
  if (history.length) {
    statusHistory.append(element("p", "thread-card-location", actionLabel(history.at(-1))));
    if (history.length > 1) {
      const details = element("details");
      details.append(element("summary", "thread-card-location", "Resolution history"));
      for (const change of history) details.append(element("p", "thread-card-location", actionLabel(change)));
      statusHistory.append(details);
    }
  }
  const comments = element("div", "thread-comments");
  thread.comments.forEach((comment) => comments.append(commentNode(comment, actions)));
  const replyForm = element("form", "thread-reply-form");
  const reply = element("textarea");
  reply.rows = 2;
  reply.maxLength = 10000;
  reply.placeholder = "Reply...";
  reply.setAttribute("aria-label", "Reply to thread");
  reply.required = true;
  const replyActions = element("div", "composer-actions");
  const replyButton = element("button", "", "Reply");
  replyButton.type = "submit";
  replyActions.append(replyButton);
  replyForm.append(reply, replyActions);
  replyForm.addEventListener("click", stopCardClick);
  replyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    replyButton.disabled = true;
    try {
      const result = await actions.reply(thread, reply.value);
      if (result === true) reply.value = "";
    } finally {
      replyButton.disabled = false;
    }
  });
  const controls = element("div", "thread-controls");
  const resolution = element(
    "button",
    "quiet-control resolve-control",
    thread.status === "resolved" ? "Reopen" : "Resolve"
  );
  resolution.type = "button";
  resolution.addEventListener("click", async (event) => {
    stopCardClick(event);
    await actions.resolution(thread);
  });
  controls.append(element("span", "thread-card-location", `${thread.comments.length} comment${thread.comments.length === 1 ? "" : "s"}`));
  if (actions.canMutate) controls.append(resolution);
  if (!replyForms.has(thread.thread_id)) replyForms.set(thread.thread_id, replyForm);
  statusHistory.addEventListener("click", stopCardClick);
  card.append(header, statusHistory, comments);
  if (actions.canMutate) card.append(replyForms.get(thread.thread_id));
  card.append(controls);
  const select = () => actions.select(thread, true);
  card.addEventListener("click", select);
  card.addEventListener("keydown", (event) => {
    if (event.target !== card) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      select();
    }
  });
  return card;
}

export function renderThreadSidebar(container, threads, selectedThreadId, actions) {
  const focused = container.contains(document.activeElement) ? document.activeElement : null;
  const start = focused?.selectionStart;
  const end = focused?.selectionEnd;
  container.replaceChildren();
  threads.forEach((thread) => {
    const marker = element("button", "thread-marker");
    marker.type = "button";
    marker.hidden = true;
    marker.dataset.threadId = thread.thread_id;
    marker.setAttribute("aria-label", `Open thread on ${pageLabel(thread)}: ${thread.comments[0]?.author.display_name || "reviewer"}`);
    marker.title = `${pageLabel(thread)}: ${thread.comments[0]?.body || "Review thread"}`;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS(svg.namespaceURI, "path");
    path.setAttribute("d", "M4 4h16v12H9l-5 4z M8 8h8 M8 12h5");
    svg.append(path);
    marker.append(svg);
    if (thread.comments.length > 1) marker.append(element("span", "", String(thread.comments.length)));
    marker.addEventListener("click", () => actions.select(thread, true));
    container.append(marker, threadCard(thread, selectedThreadId, actions));
  });
  if (focused?.isConnected) {
    focused.focus({ preventScroll: true });
    if (typeof start === "number") focused.setSelectionRange(start, end);
  }
}
