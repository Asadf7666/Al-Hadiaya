/* Planning, purchase orders and backup restore. */
iconPaths.planning = iconPaths.purchases;
pages.planning = 'Planning & procurement';
function planningPage() {
  const rows = S.inventory_planning || [],
    orders = S.purchase_orders || [];
  return (
    heading(
      'PLAN & PURCHASE',
      'Keep the shelves ready.',
      'Recommendations use 30-day sales and ingredient consumption, lead time, safety stock and open purchase orders.',
      `<button class="btn secondary" onclick="planningPolicy()">Stock policy</button><button class="btn" onclick="purchaseOrderForm()">＋ Purchase order</button>`,
    ) +
    `<div class="help">Orders are estimates. Stock and supplier balances change only when goods are received and a purchase invoice is saved. Quantities are rounded to pack sizes. Without sales history, recommendations use safety stock. Café materials can be transferred from Warehouse.</div><div class="card"><div class="card-head"><h2>Stock alerts</h2></div>${table(
      ['Alert', 'Details'],
      (S.stock_alerts || []).map(
        (a) =>
          `<tr><td><span class="pill warn">${esc(a.kind.replaceAll('_', ' '))}</span></td><td style="white-space:pre-line">${esc(a.message)}</td></tr>`,
      ),
    )}</div><div class="card"><div class="card-head"><h2>Replenishment plan</h2></div>${table(
      ['Product / location', 'Available / incoming', 'Daily use / supply', 'Suggested / estimated', ''],
      rows.map(
        (r) =>
          `<tr><td>${esc(r.name)}<small>${esc(r.location)}</small></td><td>${qty(r.stock)} / ${qty(r.incoming)} ${esc(r.unit)}</td><td>${qty(r.daily_demand)} / ${r.days_remaining ?? 'No history'} days</td><td>${qty(r.recommended)} ${esc(r.unit)}<small>${rupee(r.estimated_cost)}${r.transfer_available ? ' · transfer ' + qty(r.transfer_available) + ' available' : ''}</small></td><td><button class="text-btn" onclick="planningPolicy(${r.product_id},'${r.location}')">Policy</button>${r.recommended ? `<button class="text-btn" onclick="purchaseOrderForm(${r.product_id},'${r.location}')">Order</button>` : ''}</td></tr>`,
      ),
    )}</div><div class="card"><div class="card-head"><h2>Purchase orders</h2></div>${table(
      ['Reference', 'Supplier / location', 'Status', 'Estimate', ''],
      orders.map(
        (o) =>
          `<tr><td>${esc(o.id)}<small>${date(o.created)}</small></td><td>${esc(party(o.supplier_id)?.name)}<small>${esc(o.location)}</small></td><td>${esc(o.status.replaceAll('_', ' '))}</td><td>${rupee(o.total)}</td><td><button class="text-btn" onclick="viewPurchaseOrder('${esc(o.id)}')">Review</button></td></tr>`,
      ),
    )}</div>`
  );
}
function planningPolicy(pid, loc = 'Warehouse') {
  const old = (S.inventory_plans || []).find((p) => p.product_id == pid && p.location === loc) || {};
  formModal(
    'Stock planning policy',
    `${dropdown(
      'Product',
      'product_id',
      S.products.filter((p) => p.kind !== 'recipe').map((p) => ({ value: p.id, label: p.name })),
      pid,
    )}${dropdown('Location', 'location', ['Warehouse', 'Outlet'], loc)}${dropdown('Preferred supplier', 'supplier_id', [{ value: '', label: 'Choose when ordering' }, ...S.parties.filter((p) => p.kind === 'supplier').map((p) => ({ value: p.id, label: p.name }))], old.supplier_id || '')}<div class="form-grid">${field('Supplier lead time (days)', 'lead_days', old.lead_days ?? 2, 'number', 'min="0" max="365" required')}${field('Days to cover', 'cover_days', old.cover_days ?? 14, 'number', 'min="1" max="365" required')}${field('Safety stock (base units)', 'safety_stock', old.safety_stock ?? product(pid)?.minimum ?? 0, 'number', 'min="0" step="any" required')}</div><label class="check"><input type="checkbox" name="enabled" ${old.enabled === 0 ? '' : 'checked'}> Include in replenishment planning</label>`,
    (d) => mutate('inventory_plan', { ...d, enabled: d.enabled === 'on' }, 'Planning policy saved.'),
  );
}
function purchaseOrderForm(pid, loc = 'Warehouse') {
  if (!S.parties.some((p) => p.kind === 'supplier')) return partyForm('supplier');
  const r = (S.inventory_planning || []).find((r) => r.product_id == pid && r.location === loc);
  formModal(
    'Draft purchase order',
    `${dropdown(
      'Supplier',
      'supplier_id',
      S.parties.filter((p) => p.kind === 'supplier').map((p) => ({ value: p.id, label: p.name })),
      r?.supplier_id,
    )}${dropdown('Receive at', 'location', ['Warehouse', 'Outlet'], loc)}${field('Order note', 'note', '')}<div id="purchase-lines"></div><button type="button" class="btn secondary small" onclick="addPurchaseLine()">＋ Add item</button><div class="help" id="purchase-total"></div>`,
    (d) => {
      const items = Array.from(document.querySelectorAll('.purchase-line'))
        .filter((row) => row.querySelector('select').value)
        .map((e) => ({
          product_id: e.querySelector('select').value,
          quantity: e.querySelector('[data-qty]').value,
          price: e.querySelector('[data-price]').value,
        }));
      return mutate('purchase_order_create', { ...d, items }, 'Draft created. No stock or supplier balance changed.');
    },
    'Save draft',
  );
  addPurchaseLine();
  if (pid) {
    const e = $('.purchase-line');
    selectPurchaseProduct(e, pid);
    e.querySelector('[data-qty]').value = r?.recommended || product(pid).pack;
    e.querySelector('[data-price]').value = product(pid).cost / 100;
    purchaseTotal();
  }
}
function viewPurchaseOrder(id) {
  const o = S.purchase_orders.find((o) => o.id === id);
  openModal(
    'Purchase order ' + id,
    `${table(
      ['Item', 'Ordered', 'Received', 'Remaining'],
      JSON.parse(o.items).map(
        (i) =>
          `<tr><td>${esc(i.name)}</td><td>${qty(i.quantity)} ${esc(i.unit)}</td><td>${qty(i.received)}</td><td>${qty(i.quantity - i.received)}</td></tr>`,
      ),
    )}<p>${esc(o.note)}</p><div class="help">Estimated ${rupee(o.total)}. Confirm actual supplier invoice costs and payment when receiving. Sync before receiving against a shared order.</div>`,
    `${o.status === 'draft' ? `<button class="btn" onclick="poStatus('${id}','approved')">Approve</button>` : ''}${o.status === 'approved' ? `<button class="btn secondary" onclick="poStatus('${id}','sent')">Mark sent to supplier</button>` : ''}${['approved', 'sent', 'part_received'].includes(o.status) ? `<button class="btn" onclick="receivePurchaseOrder('${id}')">Receive goods</button>` : ''}${['draft', 'approved', 'sent', 'part_received'].includes(o.status) ? `<button class="btn danger" onclick="poStatus('${id}','cancelled')">Cancel remaining</button>` : ''}<button class="btn secondary" onclick="closeModal()">Close</button>`,
  );
}
async function poStatus(id, status) {
  try {
    await mutate('purchase_order_status', { id, status }, 'Purchase order updated.');
    closeModal();
  } catch (e) {
    toast(e.message, true);
  }
}
function receivePurchaseOrder(id) {
  const o = S.purchase_orders.find((o) => o.id === id);
  closeModal();
  purchaseForm();
  const form = $('#modal form');
  form.elements.party_id.value = o.supplier_id;
  form.elements.location.value = o.location;
  const hidden = document.createElement('input');
  hidden.type = 'hidden';
  hidden.name = 'purchase_order_id';
  hidden.value = id;
  form.appendChild(hidden);
  $('#purchase-lines').innerHTML = '';
  for (const i of JSON.parse(o.items).filter((i) => i.received < i.quantity)) {
    addPurchaseLine();
    const e = Array.from(document.querySelectorAll('.purchase-line')).at(-1);
    selectPurchaseProduct(e, i.product_id);
    e.querySelector('[data-qty]').value = i.quantity - i.received;
    e.querySelector('[data-price]').value = i.cost / 100;
  }
  purchaseTotal();
  toast('Receiving ' + id + '. Reduce quantities for a partial delivery; enter actual supplier reference and costs.');
}
function restoreForm() {
  formModal(
    'Restore business backup',
    `<p>Restore a backup ZIP containing the database and photographs. This replaces business records after making a safety backup. Accounts on this PC are preserved; you will sign in again.</p><div class="notice">Paired or folder-synced PCs require assisted recovery to avoid replaying old transactions.</div><label>Backup ZIP<input id="restore-file" type="file" accept=".zip" required></label>${field('Type RESTORE to confirm', 'confirm', '', 'text', 'pattern="RESTORE" required')}`,
    async (d) => {
      const f = $('#restore-file').files[0];
      if (!f) throw Error('Choose a backup ZIP.');
      if (f.size > 64 * 1024 * 1024) throw Error('Use assisted recovery for backups above 64 MB.');
      const content = await new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(r.result.split(',')[1]);
        r.onerror = reject;
        r.readAsDataURL(f);
      });
      await api('restore_bundle', { confirm: d.confirm, content });
      location.href = '/login';
    },
    'Back up & restore',
  );
}
