const form = document.getElementById('invitation-open');
if (form) {
  const token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
  // A fragment never reaches HTTP access logs; remove it from the visible history too.
  history.replaceState(null, '', location.pathname);
  if (/^[a-f0-9]{64}$/.test(token)) {
    form.elements.token.value = token;
    form.querySelector('button').disabled = false;
    form.querySelector('[role=status]').textContent = '';
  } else {
    form.querySelector('[role=status]').textContent = 'This link is incomplete. Ask the inviter to copy a new invitation link.';
  }
}
document.querySelector('[data-copy-invitation]')?.addEventListener('click', async () => {
  const input = document.getElementById('invitation-link');
  const status = document.querySelector('[data-copy-status]');
  try {
    await navigator.clipboard.writeText(input.value);
    status.textContent = ' Link copied.';
  } catch {
    input.focus(); input.select();
    status.textContent = ' Copy the selected link.';
  }
});
