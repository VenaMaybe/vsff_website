import { appFetch } from "./http.js";
export class ReviewApiError extends Error {
  constructor(message, status = 0, code = "request_failed") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function jsonRequest(url, options = {}) {
  const response = await appFetch(url, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ReviewApiError(
      data?.error?.message || "PDF Review could not complete the review request.",
      response.status,
      data?.error?.code
    );
  }
  return data;
}

export async function fetchThreads(url) {
  return (await jsonRequest(url)).threads;
}

export async function createThread(url, anchor, body) {
  return (await jsonRequest(url, {
    method: "POST",
    body: JSON.stringify({ anchor, body }),
  })).thread;
}

export async function addReply(url, body) {
  return (await jsonRequest(url, {
    method: "POST",
    body: JSON.stringify({ body }),
  })).thread;
}

export async function editComment(url, body, expectedRevision) {
  return (await jsonRequest(url, {
    method: "PATCH",
    body: JSON.stringify({ body, expected_revision: expectedRevision }),
  })).thread;
}

export async function deleteComment(url) {
  return (await jsonRequest(url, { method: "DELETE" })).thread;
}

export async function changeResolution(url) {
  return (await jsonRequest(url, { method: "POST" })).thread;
}

export async function fetchReviewers(url) {
  return jsonRequest(url);
}
