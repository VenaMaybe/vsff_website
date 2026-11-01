import { appFetch } from "./http.js";
export class AnchorApiError extends Error {
  constructor(message, status = 0, code = "request_failed") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function jsonRequest(url, options = {}) {
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
    throw new AnchorApiError(
      data?.error?.message || "PDF Review could not complete the anchor request.",
      response.status,
      data?.error?.code
    );
  }
  return data;
}

export async function fetchAnchors(url) {
  return (await jsonRequest(url)).anchors;
}

export async function saveAnchor(url, payload) {
  return (await jsonRequest(url, { method: "POST", body: JSON.stringify(payload) })).anchor;
}

export async function removeAnchor(url) {
  return jsonRequest(url, { method: "DELETE" });
}
