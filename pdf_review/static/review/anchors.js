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
import { renderThreadSidebar, scrollThreadIntoView } from "./thread_sidebar.js";

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
const presence = new ReviewPresence(config.versionId, document.getElementById("review-presence"));
const threadRefresh = new RefreshCoordinator(
  () => fetchThreads(config.threadsUrl),
  (threads) => { state.setThreads(threads); refreshAll(); migrationUI?.refresh.request(); },
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
    return await mutateThread(
      () => addReply(threadCommentsUrl(thread.thread_id), body),
      thread.thread_id,
      "Reply added."
    );
  },
  edit: async (comment, body) => {
    return await mutateThread(
      () => editComment(commentUrl(comment.comment_id), body, comment.current_revision),
      comment.thread_id,
      "Comment updated."
    );
  },
  currentComment: (commentId) => state.threads.flatMap((thread) => thread.comments).find((comment) => comment.comment_id === commentId),
  remove: async (comment) => {
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
  renderThreadSidebar(
    threadList,
    state.visibleThreads(),
    state.selectedThreadId,
    sidebarActions
  );
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
  state.selectedThreadId = threadId;
  refreshSidebar();
  refreshOverlay();
  scrollThreadIntoView(threadList, threadId);
  if (navigate) {
    const anchor = threadAnchor(thread);
    if (anchor) overlay?.navigateTo(anchor);
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
    scrollThreadIntoView(threadList, selectedThreadId);
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
  saveButton.disabled = !ready || !config.canMutate;
  migrationUI?.selectionChanged(ready ? pendingSelection : null);
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
      composer.close();
      threadRefresh.invalidate();
      state.replaceThread(thread);
      state.selectedThreadId = thread.thread_id;
      refreshAll();
      selectThread(thread.thread_id, true);
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
  if (!state.currentReviewer) {
    setReviewStatus("Sign in to comment.", "error");
    return;
  }
  const payload = captureCurrentSelection();
  if (!payload) {
    setReviewStatus(CAPTURE_ERROR, "error");
    return;
  }
  composer.open(payload);
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
  frame.contentDocument.addEventListener("selectionchange", rememberSelection);
  refreshAll();
  if (config.migrationUrl) migrationUI = new MigrationSidebar(config.migrationUrl, captureCurrentSelection, () => threadRefresh.request(), config.isOwner);
  if (config.initialThreadId) selectThread(config.initialThreadId, true);
  realtime = new ReviewRealtime(config.versionId, threadRefresh, presence, document.getElementById("realtime-status"), (event) => {
    if (event.migration_id === migrationUI?.run?.migration_id) migrationUI.refresh.request();
  });
  presence.watch(viewerApplication, (page) => {
    if (realtime.joined) realtime.socket.emit("review.page", { page });
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
