// Refresh only the authorized document list; preserve any document-title draft.
const createdDate = new Intl.DateTimeFormat(undefined, {dateStyle:'medium', timeStyle:'short'});
function formatDates(root) {
  for (const time of root.querySelectorAll('.document-metadata time[datetime]')) {
    const date = new Date(time.dateTime);
    if (!Number.isNaN(date.getTime())) time.textContent = createdDate.format(date);
  }
}
formatDates(document);
let refreshing = false;
async function refreshDocuments() {
  if (document.hidden || refreshing) return;
  refreshing = true;
  try {
    const response = await fetch(location.pathname, {credentials: 'same-origin', cache: 'no-store'});
    if (response.redirected || !response.ok) return;
    const page = new DOMParser().parseFromString(await response.text(), 'text/html');
    const next = page.querySelector('.document-grid'), current = document.querySelector('.document-grid');
    // Compare the same presentation so formatting cannot cause refresh flicker.
    if (next) formatDates(next);
    if (next && current && next.innerHTML !== current.innerHTML) current.replaceChildren(...next.childNodes);
  } catch { /* Keep the current list during network failures. */ }
  finally { refreshing = false; }
}
setInterval(refreshDocuments, 15000);
window.addEventListener('focus', refreshDocuments);
document.addEventListener('visibilitychange', refreshDocuments);
