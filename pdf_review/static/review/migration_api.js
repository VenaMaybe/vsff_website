import { jsonRequest } from "./thread_api.js";

export async function fetchMigration(url) { return (await jsonRequest(url)).migration; }
export async function migrationAction(url, payload) {
  return (await jsonRequest(url, { method: "POST", body: JSON.stringify(payload) })).migration;
}
export async function fetchTargetHistory(threadId) {
  return (await jsonRequest(`/api/threads/${encodeURIComponent(threadId)}/targets`)).targets;
}
