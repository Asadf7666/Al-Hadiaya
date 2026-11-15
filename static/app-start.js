/* Start-up: clock, session and first load. Loaded last so every screen is defined first. */
tick();
setInterval(tick, 30000);
(async () => {
  try {
    token = (await (await fetch('/api/session')).json()).token;
    await load();
  } catch (e) {
    $('#main').innerHTML = heading('APP CONNECTION', 'Open the local app first.', esc(e.message));
  }
})();
setInterval(async () => {
  if (!S || $('#modal').open || cart.length || page === 'settings' || page === 'billing') return;
  try {
    await load();
  } catch {}
}, 30000);
