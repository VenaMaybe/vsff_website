// Refresh only the authorized document list; preserve any document-title draft.
let refreshing = false;
async function refreshDocuments() {
  if (document.hidden || refreshing) return;
  refreshing = true;
  try {
    const response = await fetch(location.pathname, {credentials: 'same-origin', cache: 'no-store'});
    if (response.redirected || !response.ok) return;
    const page = new DOMParser().parseFromString(await response.text(), 'text/html');
    const next = page.querySelector('.document-grid'), current = document.querySelector('.document-grid');
    if (next && current && next.innerHTML !== current.innerHTML) current.replaceChildren(...next.childNodes);
  } catch { /* Keep the current list during network failures. */ }
  finally { refreshing = false; }
}
setInterval(refreshDocuments, 15000);
window.addEventListener('focus', refreshDocuments);
document.addEventListener('visibilitychange', refreshDocuments);
