// Shared same-origin mutation CSRF transport for every app-owned API module.
export function appFetch(url, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  if (["POST", "PATCH", "PUT", "DELETE"].includes(method)) {
    headers.set("X-CSRF-Token", document.querySelector('meta[name="csrf-token"]')?.content || "");
  }
  return fetch(url, { ...options, headers, credentials: "same-origin" });
}
