/* Supplier purchases and the purchase entry form. */
function purchases() {
  return (
    heading(
      'SUPPLIER PURCHASES',
      'Stock coming in.',
      'Receive bottles, cases and ingredients. Keep supplier dues in view.',
      `<button class="btn" onclick="purchaseForm()">＋ Receive purchase</button>`,
    ) +
    `<div class="stats">${stat(
      'Purchases recorded',
      rupee(
        sum(
          liveDocs().filter((d) => d.kind === 'purchase'),
          'total',
        ),
      ),
      '↓',
      'All recorded supplier purchases',
    )}${stat(
      'Supplier dues',
      rupee(
        sum(
          S.parties.filter((p) => p.kind === 'supplier'),
          'balance',
        ),
      ),
      '↗',
      'Outstanding purchase credit',
    )}${stat('Suppliers', S.parties.filter((p) => p.kind === 'supplier').length, '♙', 'Your purchase partners')}${stat(
      'Warehouse stock value',
      rupee(
        sum(
          S.stocks.filter((s) => s.location === 'Warehouse'),
          (s) => s.quantity * (product(s.product_id)?.cost || 0),
        ),
      ),
      '▣',
      'At average acquisition cost',
    )}</div><div class="card"><div class="card-head"><h2>Purchase history</h2><button class="text-btn" onclick="partyForm('supplier')">＋ Add supplier</button></div>${documentTable(S.documents.filter((d) => d.kind === 'purchase').slice(0, 100))}<p class="entry-hint" style="padding:12px">Latest 100 records · F9 searches the full purchase history</p></div>`
  );
}
function purchaseForm() {
  if (!S.parties.some((p) => p.kind === 'supplier')) return partyForm('supplier');
  purchaseCart = [];
  formModal(
    'Receive supplier purchase',
    `${dropdown(
      'Supplier',
      'party_id',
      S.parties.filter((p) => p.kind === 'supplier').map((p) => ({ value: p.id, label: p.name })),
    )}<div class="form-grid">${dropdown('Receive at', 'location', ['Warehouse', 'Outlet'], S.settings.device_location || 'Warehouse')}${field('Supplier invoice reference', 'reference', '', 'text', 'required')}</div><label>Purchase items</label><div class="help">F3 scans/searches a product. Enter moves to quantity and cost, then starts the next item. Alt+C sets one case; Alt+P goes to the amount paid. Ctrl+Enter saves after review. Unit cost is the cost for one bottle/pack, including tax. Add one line per lot when a delivery has different expiry dates.</div><div id="purchase-lines"></div><button type="button" class="btn secondary small" onclick="addPurchaseLine()">＋ Add item</button><div class="form-grid" style="margin-top:20px">${dropdown('Payment method', 'payment', ['Cash', 'UPI', 'Card', 'Bank'], 'Cash')}${field('Amount paid ₹', 'paid', 0, 'number', 'min="0" step="0.01" required')}</div><div class="help" id="purchase-total">Add the products on the supplier’s invoice. Stock increases and the unpaid amount becomes a supplier due.</div>`,
    async (data) => {
      const items = Array.from(document.querySelectorAll('.purchase-line'))
        .filter((row) => row.querySelector('select').value)
        .map((el) => ({
          product_id: el.querySelector('select').value,
          quantity: el.querySelector('[data-qty]').value,
          price: el.querySelector('[data-price]').value,
          lot: el.querySelector('[data-lot]').value,
          expiry: el.querySelector('[data-expiry]').value,
          mrp: el.querySelector('[data-mrp]').value,
        }));
      await mutate('purchase', { ...data, items }, 'Purchase saved. Stock and supplier ledger updated.');
    },
  );
  addPurchaseLine();
}
function selectPurchaseProduct(row, id) {
  clearTimeout(row.choiceTimer);
  const p = product(id);
  if (!p || p.kind === 'recipe') return false;
  const select = row.querySelector('select');
  select.innerHTML = `<option value="${p.id}">${esc(p.name)}</option>`;
  select.value = p.id;
  const search = row.querySelector('[data-purchase-search]');
  search.value = p.name;
  search.setCustomValidity('');
  search.setAttribute('aria-expanded', 'false');
  row.querySelector('[data-purchase-results]').hidden = true;
  row.querySelector('[data-price]').value = p.cost / 100;
  if (p.mrp) row.querySelector('[data-mrp]').value = p.mrp / 100;
  purchaseTotal();
  return true;
}
function purchaseChoices(row) {
  clearTimeout(row.choiceTimer);
  const input = row.querySelector('[data-purchase-search]'),
    host = row.querySelector('[data-purchase-results]');
  const term = input.value.trim(),
    exact = scanProduct(term);
  const rows = (exact ? [exact] : matchingProducts(term)).filter((p) => p.kind !== 'recipe').slice(0, 20);
  row.purchaseChoices = rows;
  row.purchaseChoice = 0;
  host.innerHTML =
    rows
      .map(
        (p, i) =>
          `<button type="button" role="option" id="purchase-choice-${row.dataset.row}-${i}" data-choice="${i}" aria-selected="${i === 0}"><strong>${esc(p.name)}</strong><small>${esc(p.sku)} · ${esc(p.barcode)}</small></button>`,
      )
      .join('') || '<p>No matching products. Check the barcode or add it in Inventory.</p>';
  host.hidden = false;
  input.setAttribute('aria-expanded', 'true');
  input.setAttribute('aria-activedescendant', rows.length ? `purchase-choice-${row.dataset.row}-0` : '');
  host.querySelectorAll('button').forEach(
    (button) =>
      (button.onclick = () => {
        selectPurchaseProduct(row, rows[Number(button.dataset.choice)].id);
        const field = row.querySelector('[data-qty]');
        field.focus();
        field.select();
      }),
  );
}
let purchaseRowSequence = 0;
function addPurchaseLine() {
  const host = $('#purchase-lines');
  if (!host) return;
  if (host.children.length >= 101) return toast('A purchase supports up to 100 selected items.', true);
  const el = document.createElement('div');
  el.className = 'purchase-line form-grid';
  el.dataset.row = ++purchaseRowSequence;
  el.style.cssText = 'padding:13px;background:#f7f8f4;border-radius:6px;margin:10px 0';
  el.innerHTML = `<div class="field span2"><label for="purchase-search-${el.dataset.row}">Product name, SKU or barcode · F3</label><input id="purchase-search-${el.dataset.row}" data-purchase-search autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="purchase-results-${el.dataset.row}" placeholder="Scan or search, then Enter"><select hidden aria-label="Selected purchase product"><option value=""></option></select><div id="purchase-results-${el.dataset.row}" data-purchase-results role="listbox" aria-label="Matching purchase products" class="entry-results" hidden></div></div><div style="margin-bottom:12px"><label>Lot / batch no. (optional)</label><input data-lot maxlength="40" autocomplete="off" placeholder="As printed on the pack"></div><div style="margin-bottom:12px"><label>Expiry date (optional)</label><input data-expiry type="date"></div><div style="margin-bottom:12px"><label>MRP on this lot ₹ (optional)</label><input data-mrp type="number" min="0" step="0.01" placeholder="As printed on the pack"></div><div><label>Quantity (base units)</label><input data-qty type="number" min="0.001" step="any" value="1" oninput="purchaseTotal()" required></div><div><label>Unit cost ₹ (incl. tax)</label><input data-price type="number" min="0" step="0.01" value="0" oninput="purchaseTotal()" required></div><div class="actions"><button type="button" class="text-btn" onclick="const e=this.closest('.purchase-line'),p=product(e.querySelector('select').value);if(p){e.querySelector('[data-qty]').value=p.pack;purchaseTotal();}">Set 1 case / pack · Alt+C</button><button type="button" class="text-btn" onclick="const row=this.closest('.purchase-line');row.remove();purchaseTotal();document.querySelector('[data-purchase-search]')?.focus()">Remove</button></div>`;
  host.appendChild(el);
  const input = el.querySelector('[data-purchase-search]');
  input.oninput = () => {
    el.querySelector('select').innerHTML = '<option value=""></option>';
    input.setCustomValidity(input.value.trim() ? 'Choose a product from the results, or scan an exact code and press Enter.' : '');
    el.purchaseChoices = [];
    clearTimeout(el.choiceTimer);
    el.choiceTimer = setTimeout(() => {
      if (el.isConnected) purchaseChoices(el);
    }, 60);
    purchaseTotal();
  };
  purchaseTotal();
  return el;
}

function purchaseTotal() {
  const total = Array.from(document.querySelectorAll('.purchase-line')).reduce(
    (n, el) =>
      n +
      (el.querySelector('select').value
        ? Math.round(Number(el.querySelector('[data-qty]').value) * Number(el.querySelector('[data-price]').value) * 100)
        : 0),
    0,
  );
  $('#purchase-total').textContent = 'Purchase total: ' + rupee(total) + ' · Enter the amount paid; the remainder becomes supplier credit.';
}
