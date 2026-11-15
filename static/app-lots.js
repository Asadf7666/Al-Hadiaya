/* Lots with expiry and MRP, and the history window. */
function productLots(id, location) {
  return (S.lots || []).filter((l) => l.product_id === id && (!location || l.location === location));
}
function lotStatus(l) {
  return l.status === 'expired'
    ? ['red', 'Expired']
    : l.status === 'near'
      ? ['warn', l.days === 0 ? 'Expires today' : `${l.days} days left`]
      : l.status === 'ok'
        ? ['', 'In date']
        : ['', 'No expiry'];
}
function lotNote(id) {
  const lots = productLots(id).filter((l) => l.expiry);
  if (!lots.length) return '';
  return ` · ${lots.length} lot${lots.length > 1 ? 's' : ''}, next expiry ${esc(lots[0].expiry)}`;
}
function lotPill(id) {
  const lots = productLots(id);
  return lots.some((l) => l.status === 'expired')
    ? ' <span class="pill red">Expired lot</span>'
    : lots.some((l) => l.status === 'near')
      ? ' <span class="pill warn">Expiring soon</span>'
      : '';
}
function lotList(id) {
  const p = product(id),
    lots = productLots(id),
    tracked = (l) => lots.filter((x) => x.location === l).reduce((n, x) => n + x.quantity, 0);
  const loose = ['Warehouse', 'Outlet'].map((l) => [l, stock(id, l) - tracked(l)]).filter(([, n]) => n > 0.000001);
  openModal(
    'Lots · ' + esc(p.name),
    table(
      ['Lot / batch', 'Expiry', 'MRP', 'Location', 'Quantity', 'Status'],
      lots
        .map((l) => {
          const [tone, label] = lotStatus(l);
          return `<tr><td><strong>${esc(l.lot || 'No lot number')}</strong></td><td>${esc(l.expiry || '—')}</td><td>${l.mrp ? rupee(l.mrp) : '—'}</td><td>${esc(l.location)}</td><td>${qty(l.quantity)} ${esc(p.unit)}</td><td><span class="pill ${tone}">${label}</span></td></tr>`;
        })
        .concat(
          loose.map(
            ([l, n]) =>
              `<tr><td>Stock without a lot</td><td>—</td><td>—</td><td>${l}</td><td>${qty(n)} ${esc(p.unit)}</td><td><span class="pill">No expiry</span></td></tr>`,
          ),
        ),
    ) +
      '<div class="help">Sales and café recipes use the earliest-expiring lot first. Expired lots are held back until written off or returned.</div>',
    `<button class="btn secondary" onclick="closeModal()">Close</button>`,
  );
}
function lotPicker(label) {
  return `<div class="field"><label for="f-lot_id">${label}</label><select id="f-lot_id" name="lot_id"><option value="">Earliest expiry first</option></select></div>`;
}
function bindLotPicker(locationField) {
  const product = $('#f-product_id'),
    place = $('#f-' + locationField),
    picker = $('#f-lot_id');
  if (!product || !place || !picker) return;
  const fill = () => {
    const lots = productLots(Number(product.value), place.value);
    picker.innerHTML =
      '<option value="">Earliest expiry first</option>' +
      lots
        .map(
          (l) =>
            `<option value="${l.id}">${esc(l.lot || 'No lot number')} · ${esc(l.expiry || 'no expiry')} · ${qty(l.quantity)}${l.status === 'expired' ? ' · expired' : ''}</option>`,
        )
        .join('');
    picker.disabled = !lots.length;
  };
  product.addEventListener('change', fill);
  place.addEventListener('change', fill);
  fill();
}
/* History window: screens load recent transactions first and fetch older ones on request. */
function historyNote() {
  return S.history && !S.history.complete
    ? `<div class="notice history-note">Showing records since ${date(S.history.since)}, plus every unpaid bill. <button type="button" class="text-btn" onclick="loadOlder()">Load all older records</button></div>`
    : '';
}
async function loadOlder(from = '2000-01-01') {
  historySince = from;
  await load();
  toast('Older records loaded.');
}
async function applyReportRange() {
  reportFrom = $('#report-from').value;
  reportTo = $('#report-to').value;
  if (S.history && !S.history.complete && (!reportFrom || reportFrom < S.history.since)) {
    historySince = reportFrom || '2000-01-01';
    await load();
  } else render();
}
