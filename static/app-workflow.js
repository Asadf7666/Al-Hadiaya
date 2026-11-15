/* Role-based overview, saved bill drafts, navigation refinements and inventory paging. */
const baseOverview = overview;
overview = function () {
  const role = S.web_user?.role || 'owner',
    tasks =
      role === 'viewer'
        ? []
        : role === 'cashier'
          ? [
              ['billing', 'New bill', 'Scan or choose products'],
              ['people', 'Customer profiles', 'Find a mobile number'],
            ]
          : [
              ['billing', 'New bill', 'Retail, wholesale or café'],
              ['purchases', 'Receive stock', 'Record supplier invoice'],
              ['planning', 'Plan & order', 'Review replenishment'],
              ['people', 'Collect or pay', 'Customer and supplier dues'],
            ];
  return (
    `<div class="task-grid">${tasks.map(([p, title, note]) => `<button class="task" onclick="navTo('${p}')"><strong>${title}</strong><span>${note}</span></button>`).join('')}</div>` +
    baseOverview()
  );
};
const flowRender = render;
render = function () {
  flowRender();
  if (draftLoaded) saveBillDraft();
  if (!$('#nav-backdrop')) {
    const b = document.createElement('button');
    b.id = 'nav-backdrop';
    b.className = 'nav-backdrop';
    b.setAttribute('aria-label', 'Close navigation');
    b.onclick = () => $('.sidebar').classList.remove('open');
    document.body.appendChild(b);
  }
  if (!$('#mobile-menu')) {
    const b = document.createElement('button');
    b.id = 'mobile-menu';
    b.className = 'btn secondary small menu-button';
    b.style.display = 'none';
    b.textContent = '☰ Menu';
    b.setAttribute('aria-label', 'Open navigation');
    b.onclick = () => $('.sidebar').classList.toggle('open');
    $('header').prepend(b);
  }
  const d = S.diagnostics || {},
    errors = S.sync_errors.length,
    mode = S.online ? 'Online workspace' : S.settings.cloud_url ? 'Server sync' : S.settings.sync_folder ? 'Folder exchange' : 'Local PC';
  const status = document.createElement('div');
  status.className = 'system-status' + (errors ? ' warn' : '');
  status.innerHTML = `<strong>${esc(mode)}${errors ? ' · ' + errors + ' conflict(s) need review' : ''}</strong><span>${S.online ? 'Internet required' : 'Billing works offline'}</span><span>${d.pending_sync != null ? d.pending_sync + ' changes waiting to sync' : ''}</span><span>${S.release_version ? 'v' + esc(S.release_version) : ''}</span><span>${(
    d.background_tasks || []
  )
    .filter((t) => t.failures > 0)
    .map((t) => esc(t.component) + ' needs attention')
    .join(' · ')}</span>`;
  $('#main').prepend(status);
};
const flowNav = navTo;
navTo = function (name) {
  $('.sidebar').classList.remove('open');
  const role = S?.web_user?.role;
  if (role === 'cashier' && !['overview', 'billing', 'people', 'staff'].includes(name))
    return toast('This screen requires a manager or owner account.', true);
  if (role === 'viewer' && !['overview', 'people', 'staff'].includes(name)) return toast('Your account is read-only.', true);
  flowNav(name);
};

function billDraftKey() {
  return 'alhadiya-bill:' + S.settings.device_id + ':' + (S.web_user?.id || 'local');
}
function saveBillDraft() {
  try {
    if (!cart.length) {
      sessionStorage.removeItem(billDraftKey());
      return;
    }
    sessionStorage.setItem(
      billDraftKey(),
      JSON.stringify({
        cart,
        party: window.saleParty || '',
        tier: window.priceTier || 'retail',
        discount: window.saleDiscount || 0,
        order: window.saleTradeOrder || '',
        location: localLocation(),
      }),
    );
  } catch {}
}
function restoreBillDraft() {
  try {
    const d = JSON.parse(sessionStorage.getItem(billDraftKey()) || 'null');
    if (!d || d.location !== localLocation()) return;
    if (d.order && !S.trade_orders.some((o) => o.id === d.order && !o.invoice_id)) {
      sessionStorage.removeItem(billDraftKey());
      toast('Saved order draft cleared because the order is already invoiced or unavailable.');
      return;
    }
    cart = d.cart
      .map((l) => ({ id: Number(l.id), quantity: Number(l.quantity) }))
      .filter((l) => product(l.id) && Number.isFinite(l.quantity) && l.quantity > 0);
    window.saleParty = S.parties.some((p) => p.id == d.party) ? d.party : '';
    window.priceTier = d.tier === 'wholesale' ? 'wholesale' : 'retail';
    window.saleDiscount = Math.max(0, Number(d.discount) || 0);
    window.saleTradeOrder = S.trade_orders.some((o) => o.id === d.order && !o.invoice_id) ? d.order : '';
    if (cart.length) toast('Unfinished bill restored. Review current prices and stock before checkout.');
  } catch {}
}

const policyNotifications = notificationsPage;
notificationsPage = function () {
  return (
    (S.settings.whatsapp_pause_reason ? '<div class="notice">' + esc(S.settings.whatsapp_pause_reason) + '</div>' : '') +
    policyNotifications()
  );
};

function disconnectServerForm() {
  formModal(
    'Disconnect server sync',
    '<p>Stop billing on every node and exchange all changes first. This PC verifies a final exchange and makes a backup. Keep the same business data on every node before switching to a shared folder. Do not use this for a temporary server shutdown.</p>' +
      field('Type DISCONNECT', 'confirm', '', 'text', 'pattern="DISCONNECT" required'),
    (d) => mutate('cloud_disconnect', d, 'Server exchange finished. Configure folder exchange if needed.'),
    'Finish exchange & disconnect',
  );
}

async function openCafePOS() {
  if (localLocation() !== 'Outlet') {
    if (cart.length) return toast('Finish or clear the current bill before switching to the café.', true);
    if (S.web_user?.role !== 'owner')
      return toast('Select an account assigned to the café outlet, or ask the owner to change your access.', true);
    try {
      await api('location', { location: 'Outlet' });
      window.saleParty = '';
      window.saleDiscount = 0;
      await load();
    } catch (e) {
      return toast(e.message, true);
    }
  }
  navTo('billing');
  category = 'Café menu';
  render();
}

function retireServerForm() {
  formModal(
    'Remove a retired server connection',
    '<p>Use this only when your server has been permanently deleted. The app creates a local backup and preserves all records, unsent changes and recovery identity. This does not recover records that exist only on another PC or on the deleted server.</p><div class="help">Sync and WhatsApp delivery will be off. Compare every PC with the saved server backup and reconcile pending transactions before enabling shared-folder exchange. Do not use this for a temporary outage.</div>' +
      field('Type RETIRED', 'confirm', '', 'text', 'pattern="RETIRED" required'),
    async (d) => {
      const r = await mutate('cloud_retire', d);
      toast(r.message);
    },
    'Back up & remove connection',
  );
}

function inventoryPageRows(rows) {
  inventoryOffset = Math.min(inventoryOffset, Math.max(0, Math.floor((rows.length - 1) / RECORD_PAGE_SIZE) * RECORD_PAGE_SIZE));
  return (
    inventoryTable(rows.slice(inventoryOffset, inventoryOffset + RECORD_PAGE_SIZE)) +
    pageControls(inventoryOffset, rows.length, RECORD_PAGE_SIZE, 'moveInventoryPage')
  );
}
function refreshInventory() {
  if ($('#inventory-results')) $('#inventory-results').innerHTML = inventoryPageRows(matchingProducts());
}
function moveInventoryPage(direction) {
  inventoryOffset = Math.max(0, inventoryOffset + direction * RECORD_PAGE_SIZE);
  refreshInventory();
  $('#inventory-results .table-wrap')?.focus();
}
