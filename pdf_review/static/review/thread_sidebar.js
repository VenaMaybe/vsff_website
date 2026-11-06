const editForms = new Map();
const replyForms = new Map();
const openReplies = new Set();
const expandedThreads = new Set();

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
  if (thread.section) return `${thread.section.name} \u00b7 ${thread.section.prompt?.trim()||'Overall thoughts'}`;
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
    if (save.disabled) return;
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
  if (thread.review_color) card.style.setProperty('--review-color',thread.review_color);
  if (thread.section) card.classList.add('section-feedback-card');
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
  const expanded = expandedThreads.has(thread.thread_id);
  thread.comments.forEach((comment, index) => {
    const node = commentNode(comment, actions);
    node.hidden = !expanded && index > 0 && index < thread.comments.length - 2;
    comments.append(node);
  });
  if (thread.comments.length > 3) {
    const toggle = element("button", "text-action thread-expand-control");
    toggle.type = "button";
    const syncExpanded = () => {
      const showAll = expandedThreads.has(thread.thread_id);
      [...comments.querySelectorAll(".thread-comment")].forEach((node, index) => { node.hidden = !showAll && index > 0 && index < thread.comments.length - 2; });
      toggle.textContent = showAll ? "Show less" : `Show all ${thread.comments.length} comments`;
      toggle.setAttribute("aria-expanded", String(showAll));
      if (showAll) comments.append(toggle);
      else comments.querySelector(".thread-comment").after(toggle);
    };
    toggle.addEventListener("click", (event) => {
      stopCardClick(event);
      if (expandedThreads.has(thread.thread_id)) expandedThreads.delete(thread.thread_id);
      else expandedThreads.add(thread.thread_id);
      syncExpanded();
    });
    syncExpanded();
  }
  if (thread.thread_id !== selectedThreadId) openReplies.delete(thread.thread_id);
  let replyForm = replyForms.get(thread.thread_id);
  if (!replyForm) {
    replyForm = element("form", "thread-reply-form");
    replyForm.id = `thread-reply-${thread.thread_id}`;
    const reply = element("textarea");
    reply.rows = 2;
    reply.maxLength = 10000;
    reply.placeholder = "Reply...";
    reply.setAttribute("aria-label", "Reply to thread");
    reply.required = true;
    replyForm.append(reply);
    replyForm.addEventListener("click", stopCardClick);
    replyForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (replyForm.dataset.busy === "true") return;
      replyForm.dataset.busy = "true";
      const submitter = replyForm.closest(".thread-card")?.querySelector(".reply-control");
      if (submitter) submitter.disabled = true;
      try {
        const result = await actions.reply(thread, reply.value);
        if (result === true) {
          reply.value = "";
          openReplies.delete(thread.thread_id);
          replyForm.hidden = true;
          const button = replyForm.closest(".thread-card")?.querySelector(".reply-control");
          if (button) {
            button.type = "button";
            button.removeAttribute("form");
            button.setAttribute("aria-expanded", "false");
            button.textContent = "Reply";
          }
        }
      } finally {
        replyForm.dataset.busy = "false";
        const button = replyForm.closest(".thread-card")?.querySelector(".reply-control");
        if (button) button.disabled = false;
      }
    });
    replyForms.set(thread.thread_id, replyForm);
  }
  replyForm.hidden = !openReplies.has(thread.thread_id);
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
  if (actions.canMutate) {
    const replyButton = element("button", "quiet-control reply-control", replyForm.hidden ? "Reply" : "Post reply");
    replyButton.type = replyForm.hidden ? "button" : "submit";
    if (!replyForm.hidden) replyButton.setAttribute("form", replyForm.id);
    replyButton.setAttribute("aria-expanded", String(!replyForm.hidden));
    replyButton.setAttribute("aria-controls", replyForm.id);
    replyButton.disabled = replyForm.dataset.busy === "true";
    replyButton.addEventListener("click", (event) => {
      stopCardClick(event);
      if (openReplies.has(thread.thread_id)) return;
      event.preventDefault();
      actions.select(thread, false);
      openReplies.add(thread.thread_id);
      replyForm.hidden = false;
      const button = replyForm.closest(".thread-card").querySelector(".reply-control");
      button.type = "submit";
      button.setAttribute("form", replyForm.id);
      button.setAttribute("aria-expanded", "true");
      button.textContent = "Post reply";
      replyForm.querySelector("textarea").focus({ preventScroll: true });
    });
    if (!thread.section) controls.append(resolution);
    if (thread.section && !thread.response_id && replyForm.hidden) replyButton.textContent='Add response';
    controls.append(replyButton);
  }
  statusHistory.addEventListener("click", stopCardClick);
  card.append(header, statusHistory, comments);
  card.append(controls);
  if (actions.canMutate) card.append(replyForm);
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
    if (thread.review_color) marker.style.setProperty('--review-color',thread.review_color);
    if (thread.section) marker.classList.add('section-feedback-marker');
    marker.setAttribute("aria-label", `Open thread on ${pageLabel(thread)}: ${thread.comments[0]?.author.display_name || "reviewer"}`);
    marker.title = `${pageLabel(thread)}: ${thread.comments[0]?.body || "Review thread"}`;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS(svg.namespaceURI, "path");
    path.setAttribute("d", "M4 4h16v12H9l-5 4z M8 8h8 M8 12h5");
    svg.append(path);
    const content = element("span", "thread-marker-content");
    content.append(svg);
    if (thread.comments.length > 1) content.append(element("span", "thread-marker-count", String(thread.comments.length)));
    marker.append(content);
    marker.addEventListener("click", () => actions.select(thread, true));
    container.append(marker, threadCard(thread, selectedThreadId, actions));
  });
  if (focused?.isConnected) {
    focused.focus({ preventScroll: true });
    if (typeof start === "number") focused.setSelectionRange(start, end);
  }
}
