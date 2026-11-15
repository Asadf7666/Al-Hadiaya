/* Café menu and recipes, customers, suppliers, payments and ledgers. */
function cafe() {
  const menu = S.products.filter((p) => p.kind === 'recipe');
  return (
    heading(
      'TAKE & GO CAFÉ',
      'A little café happiness.',
      'Manage fresh drinks and the ingredients behind every cup.',
      `<button class="btn secondary" onclick="openCafePOS()">Open café POS</button><button class="btn" onclick="productForm(null,true)">＋ Add menu item</button>`,
    ) +
    `<div class="notice">Selling a café item deducts its configured ingredients from café stock. Receive ingredients at the warehouse, then transfer them to the outlet before serving.</div><div class="product-grid">${menu
      .map((p) => {
        const r = S.recipes.filter((r) => r.product_id === p.id);
        const cost = sum(r, (r) => r.quantity * (product(r.ingredient_id)?.cost || 0));
        const available = r.length ? Math.min(...r.map((r) => Math.floor(stock(r.ingredient_id, 'Outlet') / r.quantity))) : 0;
        return `<div class="card"><div class="card-content"><span style="font-size:33px">${symbol(p.category)}</span><h3 style="margin:16px 0 9px">${esc(p.name)}</h3><p>${rupee(p.price)} <span style="font-size:11px">per ${esc(p.unit)}</span></p><p style="font-size:11px;margin-top:8px">Ingredient cost: ${rupee(cost)}<br>${available} servings available at outlet</p><div class="help">${r.length ? r.map((r) => esc(product(r.ingredient_id)?.name) + ' · ' + qty(r.quantity) + ' ' + esc(product(r.ingredient_id)?.unit)).join('<br>') : 'Set ingredients per serving before billing.'}</div><button class="btn secondary small" onclick="recipeForm(${p.id})">Set ingredients</button></div></div>`;
      })
      .join(
        '',
      )}</div>${!menu.length ? empty('Add a café menu item, then set ingredients per serving.') : ''}<div class="card" style="margin-top:24px"><div class="card-head"><h2>Café ingredients</h2><button class="text-btn" onclick="navTo('inventory')">Manage stock →</button></div>${inventoryTable(S.products.filter((p) => p.kind === 'ingredient'))}</div>`
  );
}
function recipeForm(id) {
  if (!S.products.some((p) => p.kind === 'ingredient')) return toast('Add café ingredients in Inventory first.', true);
  formModal(
    'Ingredients per serving · ' + esc(product(id).name),
    `<p style="font-size:12px;margin-bottom:18px">Quantities for one ${esc(product(id).unit)}. Include milk, syrup, coffee and packaging if you track it.</p><div id="recipe-lines"></div><button type="button" class="btn secondary small" onclick="addRecipeLine()">＋ Ingredient</button><div class="help">Quantities must use the ingredient’s base unit. For example: 200 ml soda + 30 ml mint syrup for one mojito.</div>`,
    async () => {
      const items = Array.from(document.querySelectorAll('.recipe-line')).map((el) => ({
        ingredient_id: el.querySelector('select').value,
        quantity: el.querySelector('input').value,
      }));
      await mutate('recipe', { product_id: id, items }, 'Ingredient quantities saved.');
    },
  );
  const current = S.recipes.filter((r) => r.product_id === id);
  if (current.length) current.forEach((r) => addRecipeLine(r.ingredient_id, r.quantity));
  else addRecipeLine();
}
function addRecipeLine(id, quantity = 1) {
  const el = document.createElement('div');
  el.className = 'recipe-line';
  el.innerHTML = `<select>${selectOptions(
    S.products.filter((p) => p.kind === 'ingredient').map((p) => ({ ...p, name: p.name + ' (' + p.unit + ')' })),
    id,
  )}</select><input type="number" min="0.001" step="any" value="${quantity}" required><button type="button" onclick="this.parentElement.remove()">×</button>`;
  $('#recipe-lines').appendChild(el);
}
function peopleTable(rows) {
  return table(
    ['Name', 'Contact', 'GSTIN', 'Outstanding', ''],
    rows.map(
      (p) =>
        `<tr><td><strong>${esc(p.name)}</strong><small>${esc(p.address)}</small></td><td>${esc(p.phone) || '—'}</td><td>${esc(p.gstin) || '—'}</td><td><span class="pill ${p.balance ? 'warn' : ''}">${rupee(p.balance)}</span></td><td><button class="text-btn" onclick="ledger(${p.id})">Profile & ledger</button>${canOperate('party') ? `<button class="text-btn" onclick="partyForm('${peopleFilter}',${p.id})">Edit profile</button>` : ''}${p.balance && canOperate('payment') ? `<button class="btn secondary small" onclick="paymentForm(${p.id})">${p.kind === 'customer' ? 'Collect' : 'Pay'}</button>` : ''}</td></tr>`,
    ),
  );
}
function peoplePageRows() {
  const rows = S.parties.filter(
    (p) => p.kind === peopleFilter && `${p.name} ${p.phone} ${p.gstin} ${p.address}`.toLowerCase().includes(peopleQuery.toLowerCase()),
  );
  peopleOffset = Math.min(peopleOffset, Math.max(0, Math.floor((rows.length - 1) / RECORD_PAGE_SIZE) * RECORD_PAGE_SIZE));
  return (
    peopleTable(rows.slice(peopleOffset, peopleOffset + RECORD_PAGE_SIZE)) +
    pageControls(peopleOffset, rows.length, RECORD_PAGE_SIZE, 'movePeoplePage')
  );
}
function people() {
  return (
    heading(
      'PEOPLE & LEDGERS',
      'Good relationships. Clear accounts.',
      'Search a profile, then use Down and Enter for its ledger.',
      canOperate('party') ? `<button class="btn" onclick="partyForm('${peopleFilter}')">＋ Add ${peopleFilter}</button>` : '',
    ) +
    `<div class="tabs"><button class="${peopleFilter === 'customer' ? 'active' : ''}" onclick="peopleFilter='customer';peopleQuery='';peopleOffset=0;render()">Customers</button>${['owner', 'manager'].includes(S.web_user?.role || 'owner') ? `<button class="${peopleFilter === 'supplier' ? 'active' : ''}" onclick="peopleFilter='supplier';peopleQuery='';peopleOffset=0;render()">Suppliers</button>` : ''}</div><div class="toolbar"><div class="search"><input id="people-search" value="${esc(peopleQuery)}" aria-label="Search customer or supplier profiles" placeholder="Search name, mobile or GSTIN · F3"></div></div><div class="card" id="people-results">${peoplePageRows()}</div>`
  );
}
function movePeoplePage(direction) {
  peopleOffset = Math.max(0, peopleOffset + direction * RECORD_PAGE_SIZE);
  $('#people-results').innerHTML = peoplePageRows();
  $('#people-results .table-wrap')?.focus();
}

function partyForm(kind = 'customer', id, fromBill = false) {
  const p = id ? party(id) : {};
  formModal(
    (id ? 'Edit ' : 'Add ') + kind,
    `<div class="form-grid">${field('Name / business name', 'name', p.name, 'text', 'required')}${field('Phone', 'phone', p.phone, 'tel')}${field('Email', 'email', p.email, 'email')}${field('GSTIN (optional)', 'gstin', p.gstin, 'text', 'maxlength="15"')}${field('Billing address', 'address', p.address)}${dropdown('Preferred price tier', 'price_tier', ['retail', 'wholesale'], p.price_tier || 'retail')}${field('Credit limit ₹ (0 = no preset limit)', 'credit_limit', (p.credit_limit || 0) / 100, 'number', 'min="0" step="0.01"')}${field('Customer notes', 'notes', p.notes)}${field('WhatsApp consent evidence (new consent or changed mobile)', 'whatsapp_consent_note', '', 'text', 'placeholder="How, when and for which messages did the customer agree?" maxlength="500"')}</div><label class="check"><input type="checkbox" name="whatsapp_opt_in" ${p.whatsapp_opt_in ? 'checked' : ''}> Customer agreed to WhatsApp receipts and payment notifications</label><label class="check"><input type="checkbox" name="whatsapp_marketing_opt_in" ${p.whatsapp_marketing_opt_in ? 'checked' : ''}> Customer separately agreed to promotional WhatsApp offers</label><div class="help">Editing a profile preserves its purchases, payments and outstanding balance. Credit limits follow staff permissions. Invoice details remain as issued.</div>`,
    async (data) => {
      const r = await mutate('party', { ...data, id: id || null, kind }, id ? 'Profile updated.' : kind + ' added.');
      if (fromBill && kind === 'customer' && page === 'billing') selectBillCustomer(r.id, false);
      return r;
    },
  );
}
function paymentForm(id) {
  const p = party(id);
  formModal(
    p.kind === 'customer' ? 'Record customer payment' : 'Record supplier payment',
    `<h3>${esc(p.name)}</h3><p style="margin-bottom:20px">Outstanding: ${rupee(p.balance)}</p>${field('Payment amount ₹', 'amount', p.balance / 100, 'number', 'min="0.01" step="0.01" required')}${dropdown('Payment method', 'method', ['Cash', 'UPI', 'Card', 'Bank'], 'Cash')}${field('Reference / note', 'note')}`,
    (data) => mutate('payment', { ...data, party_id: id }, 'Payment recorded. Ledger updated.'),
  );
}
function ledger(id) {
  const p = party(id),
    docs = S.documents.filter((d) => d.party_id === id),
    pay = S.payments.filter((r) => r.party_id === id);
  openModal(
    'Ledger · ' + esc(p.name),
    `<div class="report-number">${rupee(p.balance)}</div><p style="margin-bottom:23px">${p.kind === 'customer' ? 'Receivable from customer' : 'Payable to supplier'}</p>${historyNote()}<div class="notice">${esc(p.phone) || 'No phone'} · ${esc(p.email) || 'No email'}<br>${esc(p.address)}<br>${p.gstin ? 'GSTIN: ' + esc(p.gstin) + '<br>' : ''}Preferred pricing: ${esc(p.price_tier || 'retail')} · Credit limit: ${p.credit_limit ? rupee(p.credit_limit) : 'Not preset'}<br>${esc(p.notes)}</div>${table(
      ['Date', 'Entry', 'Credit / due', 'Paid / settled'],
      [
        ...docs.map((d) => ({
          date: d.date,
          entry: d.id + (d.reversed ? ' · REVERSED' : ''),
          due: d.reversed ? 0 : d.total - d.paid,
          paid: d.reversed ? 0 : d.paid,
        })),
        ...pay.map((r) => ({ date: r.date, entry: 'Payment · ' + r.method, due: -r.amount, paid: r.amount })),
      ]
        .sort((a, b) => a.date.localeCompare(b.date))
        .map((r) => `<tr><td>${date(r.date)}</td><td>${esc(r.entry)}</td><td>${rupee(r.due)}</td><td>${rupee(r.paid)}</td></tr>`),
    )}`,
  );
}
