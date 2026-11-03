import { installViewerControls, anchorGeometry, CommentRail } from "./viewer_shell.js";
import { syncMenuValues } from "./menus.js";
import { fetchAnchors, removeAnchor, saveAnchor } from "./anchor_api.js";
import { CAPTURE_ERROR } from "./anchor_constants.js";
import { renderAnchorInspector } from "./anchor_debug.js";
import { AnchorOverlay } from "./anchor_overlay.js";
import { captureTextSelection } from "./anchor_selection.js";
import { SelectionCommentComposer } from "./comment_composer.js";
import { ReviewState } from "./review_state.js";
import { RefreshCoordinator, ReviewRealtime } from "./realtime.js";
import { ReviewPresence } from "./presence.js";
import { MigrationSidebar } from "./migration_sidebar.js";
import {
  addReply,
  changeResolution,
  createThread,
  deleteComment,
  editComment,
  fetchReviewers,
  fetchThreads,
} from "./thread_api.js";
import { renderThreadSidebar } from "./thread_sidebar.js";
import { jsonRequest } from './thread_api.js';
import { SectionViewer } from './section_viewer.js';
import { ViewerPreferences } from './viewer_preferences.js';
import { registerManagement } from './management.js';

const config = JSON.parse(document.getElementById("anchor-config").textContent);
const frame = document.getElementById("pdf-viewer-frame");
const commentButton = document.getElementById("comment-selection-button");
const saveButton = document.getElementById("save-anchor-button");
const anchorStatus = document.getElementById("anchor-status");
const inspector = document.getElementById("anchor-inspector");
const reviewStatus = document.getElementById("review-status");
const threadList = document.getElementById("thread-list");
const threadFilter = document.getElementById("thread-filter");
const state = new ReviewState();
let viewerApplication = null;
let overlay = null;
let pendingSelection = null;
let captureTimer = null;
let realtime = null;
let migrationUI = null;
let retryTimer = null;
let rail = null;
let sectionViewer = null;
let viewerPreferences = null;
let selectionDismissed = false;
const presence = new ReviewPresence(config.versionId, document.getElementById("review-presence"),config.currentUserId);
const threadRefresh = new RefreshCoordinator(
  async () => {const [threads,context]=await Promise.all([fetchThreads(config.threadsUrl),jsonRequest(config.contextUrl)]);return {threads,context};},
  ({threads,context}) => { state.setThreads(threads); sectionViewer?.update(context);viewerPreferences?.update(context);refreshAll(); migrationUI?.refresh.request(); },
  () => {
    realtime?.syncFailed();
    window.clearTimeout(retryTimer);
    retryTimer = window.setTimeout(() => threadRefresh.request(), 5000);
  },
  () => { window.clearTimeout(retryTimer); realtime?.synced(); }
);

function setReviewStatus(message, kind = "") {
  reviewStatus.textContent = message;
  reviewStatus.className = `review-status ${kind}`.trim();
}

function setAnchorStatus(message, kind = "") {
  anchorStatus.textContent = message;
  anchorStatus.className = `anchor-status ${kind}`.trim();
}

function templateUrl(template, placeholder, value) {
  return template.replace(placeholder, encodeURIComponent(value));
}

function threadCommentsUrl(threadId) {
  return templateUrl(config.threadCommentsUrlTemplate, "__THREAD_ID__", threadId);
}

function commentUrl(commentId) {
  return templateUrl(config.commentUrlTemplate, "__COMMENT_ID__", commentId);
}

function resolutionUrl(thread, resolved) {
  const template = resolved ? config.resolveUrlTemplate : config.reopenUrlTemplate;
  return templateUrl(template, "__THREAD_ID__", thread.thread_id);
}

function deleteAnchorUrl(anchorId) {
  return templateUrl(config.deleteUrlTemplate, "__ANCHOR_ID__", anchorId);
}

function threadAnchor(thread) {
  return thread.targets[0]?.anchor ?? null;
}

function refreshOverlay() {
  if (!overlay) return;
  overlay.setAnchors(state.anchors);
  overlay.setThreadStates(
    state.threadStates(),
    state.selectedThreadId,
    (threadId) => selectThread(threadId, false)
  );
}

function refreshDebugInspector() {
  const commentAnchorIds = new Set(
    state.threads.flatMap((thread) => thread.targets.map((target) => target.anchor.anchor_id))
  );
  const standaloneAnchors = state.anchors.filter(
    (anchor) => !commentAnchorIds.has(anchor.anchor_id)
  );
  renderAnchorInspector(inspector, standaloneAnchors, {
    canMutate: config.canMutate,
    navigate: (anchor) => overlay?.navigateTo(anchor),
    remove: async (anchor) => {
      if (!window.confirm("Delete this test anchor? The PDF will not be changed.")) return;
      try {
        await removeAnchor(deleteAnchorUrl(anchor.anchor_id));
        state.anchors = state.anchors.filter((item) => item.anchor_id !== anchor.anchor_id);
        refreshAll();
        setAnchorStatus("Test anchor deleted.", "success");
      } catch (error) {
        setAnchorStatus(error.message, "error");
      }
    },
    viewportDetails: (pageNumber) => overlay?.currentViewportDetails(pageNumber) ?? null,
  });
}

const sidebarActions = {
  canEdit: (comment) => config.canMutate && comment.author.user_id === state.currentReviewer?.user_id,
  canMutate: config.canMutate,
  select: (thread, navigate) => selectThread(thread.thread_id, navigate),
  deselect: () => {
    state.selectedThreadId = null;
    refreshSidebar();
    refreshOverlay();
  },
  reply: async (thread, body) => {
    if(thread.section)return sectionViewer.reply(thread,body);
    return await mutateThread(
      () => addReply(threadCommentsUrl(thread.thread_id), body),
      thread.thread_id,
      "Reply added."
    );
  },
  edit: async (comment, body) => {
    if(comment.section)return sectionViewer.edit(comment,body);
    return await mutateThread(
      () => editComment(commentUrl(comment.comment_id), body, comment.current_revision),
      comment.thread_id,
      "Comment updated."
    );
  },
  currentComment: (commentId) => [...state.threads,...state.sectionThreads].flatMap((thread) => thread.comments).find((comment) => comment.comment_id === commentId),
  remove: async (comment) => {
    if(comment.section)return sectionViewer.remove(comment);
    await mutateThread(
      () => deleteComment(commentUrl(comment.comment_id)),
      comment.thread_id,
      "Comment deleted; its history was retained."
    );
  },
  resolution: async (thread) => {
    const resolving = thread.status !== "resolved";
    await mutateThread(
      () => changeResolution(resolutionUrl(thread, resolving)),
      thread.thread_id,
      resolving ? "Thread resolved." : "Thread reopened."
    );
  },
};

function refreshSidebar() {
  syncMenuValues();
  renderThreadSidebar(
    threadList,
    state.visibleThreads(),
    state.selectedThreadId,
    sidebarActions
  );
  rail?.schedule();
}

function refreshAll() {
  refreshSidebar();
  refreshDebugInspector();
  refreshOverlay();
}

function selectThread(threadId, navigate) {
  const thread = state.thread(threadId);
  if (!thread) return;
  if (thread.status === "resolved" && state.filter === "open") {
    state.filter = "all";
    threadFilter.value = "all";
  }
  rail?.freezePageWidth();
  state.selectedThreadId = threadId;
  refreshSidebar();
  refreshOverlay();
  rail?.showThread(threadId);
  if (navigate) {
    const anchor = threadAnchor(thread);
    const geometry = anchor && anchorGeometry(viewerApplication, anchor);
    // Clicking a visible highlight/card never moves the PDF. Explicit navigation
    // to a different off-screen target can still reveal that document location.
    if (anchor && (!geometry || geometry.bottom < 0 || geometry.top > rail.scroller.clientHeight)) overlay?.navigateTo(anchor);
  }
}

async function mutateThread(operation, selectedThreadId, successMessage) {
  try {
    const thread = await operation();
    threadRefresh.invalidate();
    thread.targets = thread.targets.filter((target) => target.anchor.document_version_id === config.versionId);
    state.replaceThread(thread);
    state.selectedThreadId = selectedThreadId;
    refreshAll();
    rail?.showThread(selectedThreadId);
    setReviewStatus(successMessage, "success");
    threadRefresh.request();
    return true;
  } catch (error) {
    if (error.code === "comment_conflict") await threadRefresh.request();
    setReviewStatus(error.message, "error");
    return { error };
  }
}

async function loadAnchors() {
  state.anchors = await fetchAnchors(config.anchorsUrl);
}

async function loadThreads() {
  state.setThreads(await fetchThreads(config.threadsUrl));
}

async function waitForViewer() {
  for (let attempt = 0; attempt < 400; attempt += 1) {
    const application = frame.contentWindow?.PDFViewerApplication;
    if (application) {
      await application.initializedPromise;
      if (application.pdfDocument && application.pdfViewer && application.eventBus) {
        return application;
      }
    }
    await new Promise((resolve) => window.setTimeout(resolve, 50));
  }
  throw new Error("PDF.js did not finish loading.");
}

function updateSelectionControls(ready) {
  commentButton.disabled = !ready || !config.canMutate;
  positionSelectionButton();
  saveButton.disabled = !ready || !config.canMutate;
  migrationUI?.selectionChanged(ready ? pendingSelection : null);
}

function positionSelectionButton() {
  const geometry = viewerApplication && pendingSelection && anchorGeometry(viewerApplication, pendingSelection);
  const bounds = frame.getBoundingClientRect();
  const visible = geometry && geometry.bottom > 0 && geometry.top < bounds.height && geometry.right > 0 && geometry.left < bounds.width;
  commentButton.hidden = !visible || !config.canMutate || selectionDismissed || !composer.container.hidden;
  if (commentButton.hidden) return;
  commentButton.style.left = `${Math.max(bounds.left + 4, Math.min(innerWidth - 38, bounds.left + geometry.right + 4))}px`;
  const below = bounds.top + geometry.bottom + 4;
  commentButton.style.top = `${Math.max(bounds.top + 4, Math.min(innerHeight - 36, below > innerHeight - 36 ? bounds.top + geometry.top - 34 : below))}px`;
}

function rememberSelection() {
  window.clearTimeout(captureTimer);
  captureTimer = window.setTimeout(() => {
    try {
      const selection = frame.contentWindow.getSelection();
      if (!selection || selection.isCollapsed) {
        pendingSelection = null;
        updateSelectionControls(false);
        setAnchorStatus("Select PDF text to create a test anchor.");
        return;
      }
      pendingSelection = captureTextSelection(frame.contentWindow, viewerApplication);
      selectionDismissed = false;
      updateSelectionControls(true);
      setAnchorStatus("Selection ready.");
    } catch (_error) {
      pendingSelection = null;
      updateSelectionControls(false);
    }
  }, 80);
}

function captureCurrentSelection() {
  try {
    return captureTextSelection(frame.contentWindow, viewerApplication);
  } catch (_error) {
    return pendingSelection;
  }
}

const composer = new SelectionCommentComposer(
  document.getElementById("selection-comment-composer"),
  document.getElementById("selection-comment-form"),
  document.getElementById("selection-comment-body"),
  document.getElementById("selection-comment-quote"),
  document.getElementById("cancel-selection-comment"),
  async (anchorPayload, body) => {
    if (!state.currentReviewer) {
      setReviewStatus("Sign in to comment.", "error");
      return;
    }
    composer.setBusy(true);
    try {
      const thread = await createThread(config.threadsUrl, anchorPayload, body);
      frame.contentWindow.getSelection()?.removeAllRanges();
      pendingSelection = null;
      composer.setBusy(false);
      composer.close();
      threadRefresh.invalidate();
      state.replaceThread(thread);
      state.selectedThreadId = thread.thread_id;
      refreshAll();
      selectThread(thread.thread_id, false);
      setReviewStatus("Comment added.", "success");
      threadRefresh.request();
    } catch (error) {
      setReviewStatus(error.message, "error");
    } finally {
      composer.setBusy(false);
    }
  }
);

function openCommentComposer() {
  if (!composer.container.hidden) { composer.body.focus(); return; }
  if (!state.currentReviewer) {
    setReviewStatus("Sign in to comment.", "error");
    return;
  }
  const payload = captureCurrentSelection();
  if (!payload) {
    setReviewStatus(CAPTURE_ERROR, "error");
    return;
  }
  rail?.freezePageWidth();
  sidebarActions.deselect();
  composer.open(payload);
  commentButton.hidden = true;
  rail?.schedule();
}

commentButton.addEventListener("pointerdown", () => {
  if (viewerApplication) pendingSelection = captureCurrentSelection();
});
commentButton.addEventListener("click", openCommentComposer);

saveButton.addEventListener("pointerdown", () => {
  if (viewerApplication) pendingSelection = captureCurrentSelection();
});
saveButton.addEventListener("click", async () => {
  const payload = captureCurrentSelection();
  if (!payload) {
    setAnchorStatus(CAPTURE_ERROR, "error");
    return;
  }
  saveButton.disabled = true;
  try {
    await saveAnchor(config.anchorsUrl, payload);
    frame.contentWindow.getSelection()?.removeAllRanges();
    pendingSelection = null;
    await loadAnchors();
    refreshAll();
    setAnchorStatus("Test anchor saved.", "success");
  } catch (error) {
    setAnchorStatus(error.message || CAPTURE_ERROR, "error");
  } finally {
    saveButton.disabled = false;
  }
});

threadFilter.addEventListener("change", () => {
  state.filter = threadFilter.value;
  if (state.filter === "open" && state.thread(state.selectedThreadId)?.status === "resolved") {
    state.selectedThreadId = null;
    refreshOverlay();
  }
  refreshSidebar();
});

async function initialize() {
  updateSelectionControls(false);
  const [application, reviewerData] = await Promise.all([
    waitForViewer(),
    fetchReviewers(config.reviewersUrl),
    loadAnchors(),
    loadThreads(),
  ]);
  viewerApplication = application;
  state.currentReviewer = reviewerData.current_reviewer;
  overlay = new AnchorOverlay(frame.contentWindow, viewerApplication);
  installViewerControls(frame, application);
  sectionViewer=new SectionViewer(frame,application,config,state,()=>threadRefresh.request(),setReviewStatus);
  registerManagement({config,sectionViewer,deselectThread:sidebarActions.deselect,refresh:()=>threadRefresh.request()});
  viewerPreferences=new ViewerPreferences(config,application,()=>threadRefresh.request(),setReviewStatus);
  await viewerPreferences.initialize();
  rail = new CommentRail(frame, application, state, composer, positionSelectionButton);
  await threadRefresh.request();
  new MutationObserver(() => rail.schedule()).observe(composer.container, { attributes: true, attributeFilter: ["hidden"] });
  new ResizeObserver(() => rail.schedule()).observe(composer.container);
  frame.contentDocument.addEventListener("selectionchange", rememberSelection);
  for (const doc of [document, frame.contentDocument]) {
    doc.addEventListener("click", (event) => {
      const inLeftCard = event.composedPath().some(node => node.matches?.('.left-card'));
      if (state.selectedThreadId && !inLeftCard && !event.target.closest?.(".pdf-review-thread-highlight, .thread-card, .thread-marker, #comment-selection-button, .selection-comment-composer")) {
        sidebarActions.deselect();
      }
    });
    doc.addEventListener("keydown", (event) => {
      if (event.ctrlKey && event.shiftKey && event.key === "Enter" && !event.defaultPrevented) {
        const form = event.target.closest?.(".thread-reply-form, .inline-edit-form");
        if (form && event.target.matches("textarea")) {
          event.preventDefault();
          if (form.dataset.busy !== "true" && !form.querySelector('button[type="submit"]:disabled')) form.requestSubmit();
          return;
        }
      }
      if (event.key === "Escape") {
        selectionDismissed = true;
        commentButton.hidden = true;
        if (!composer.container.hidden && !composer.busy) composer.close();
        sidebarActions.deselect();
        pendingSelection = null;
        updateSelectionControls(false);
      }
      const editing = event.target.closest?.("input, textarea, select, button, summary, a, [contenteditable=true]");
      const shortcut = (event.ctrlKey || event.metaKey) && event.altKey && event.key.toLowerCase() === "m";
      const enter = event.key === "Enter" && !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey;
      const selection = frame.contentWindow.getSelection();
      if (!editing && config.canMutate && (shortcut || enter) && selection && !selection.isCollapsed && composer.container.hidden) {
        event.preventDefault();
        event.stopPropagation();
        openCommentComposer();
      }
    });
  }
  document.addEventListener("pointerdown", (event) => {
    if (!commentButton.contains(event.target) && !composer.container.contains(event.target)) {
      selectionDismissed = true; commentButton.hidden = true;
    }
  });
  refreshAll();
  if (config.migrationUrl) migrationUI = new MigrationSidebar(config.migrationUrl, captureCurrentSelection, () => threadRefresh.request(), config.isOwner);
  if (config.initialThreadId) selectThread(config.initialThreadId, true);
  realtime = new ReviewRealtime(config.versionId, threadRefresh, presence, document.getElementById("realtime-status"), (event) => {
    if (event.migration_id === migrationUI?.run?.migration_id) migrationUI.refresh.request();
  });
  presence.watch(viewerApplication, (page,pages) => {
    if (realtime.joined) realtime.socket.emit("review.page", { page,pages });
  });
  setAnchorStatus("Select PDF text to create a test anchor.");
  setReviewStatus(
    state.currentReviewer
      ? `Reviewing as ${state.currentReviewer.display_name}.`
      : "Sign in to comment."
  );
}

initialize().catch((error) => {
  setReviewStatus(error.message || "Review tools could not start.", "error");
  setAnchorStatus(error.message || "Anchor tools could not start.", "error");
});
