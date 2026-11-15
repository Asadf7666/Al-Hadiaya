/* Overview, billing counter, basket, checkout, forms, invoices and receipts. */
function overview() {
  const sales = liveDocs().filter((d) => d.kind === 'sale' && businessDay(d.date) === today()),
    docs = liveDocs().filter((d) => d.kind === 'sale');
  const low = S.products.filter((p) => p.kind !== 'recipe' && (p.price > 0 || p.cost > 0 || p.stock > 0) && p.stock <= p.minimum),
    totalSales = sum(sales, 'total');
  return (
    heading(
      'BUSINESS AT A GLANCE',
      'A good day starts here.',
      'Everything happening at your trading warehouse and café outlet.',
      `${canOperate('backup') ? '<button class="btn secondary" onclick="runBackup()">↓ Back up data</button>' : ''}${canOperate('sale') ? '<button class="btn" onclick="navTo(\'billing\')">＋ New bill <small>F2</small></button>' : ''}`,
    ) +
    `${S.settings.demo ? '<div class="notice">Sample shop data is loaded. These are illustrative products, prices and recipes. Use a separate clean database for live trading.</div>' : ''}${S.sync_errors.length ? '<div class="help">Sync needs attention: ' + S.sync_errors.length + ' transaction(s) are waiting. Open Settings to review them.</div>' : ''}
<div class="welcome-banner"><div><strong>Chill. Refresh. Enjoy. Always.</strong><p>Cold drinks, everyday essentials & a little café happiness.</p></div><div class="banner-decoration">✦ AH</div></div>
<div class="stats">${stat('Today’s sales', rupee(totalSales), '₹', sales.length + ' bills recorded today')}${stat('Inventory value', rupee(sum(S.products, (p) => p.stock * p.cost)), '▣', 'Across warehouse & outlet')}${stat(
      'Customer dues',
      rupee(
        sum(
          S.parties.filter((p) => p.kind === 'customer'),
          'balance',
        ),
      ),
      '↗',
      'Outstanding customer credit',
    )}${stat('Low-stock products', low.length, '◷', low.length ? 'Review your reorder list' : 'Your shelves are in good shape')}</div>
<div class="dashboard-grid"><div class="card"><div class="card-head"><div><h2>Sales this week</h2><p>Your last 7 days, across both locations</p></div><span class="pill">${docs.length} total bills</span></div>${chart(docs)}</div><div class="card"><div class="card-head"><div><h2>Your business, together</h2><p>Two locations. One clear picture.</p></div></div><div class="mix-item"><div class="mix-icon">▣</div><div><strong>Trading warehouse</strong><small>${S.stocks.filter((s) => s.location === 'Warehouse' && s.quantity > 0).length} stocked SKUs · direct customer billing</small></div><b>${rupee(
      sum(
        S.stocks.filter((s) => s.location === 'Warehouse'),
        (s) => s.quantity * (product(s.product_id)?.cost || 0),
      ),
    )}</b></div><div class="mix-item"><div class="mix-icon">▤</div><div><strong>Café / shop outlet</strong><small>Takeaway café & packaged-goods billing</small></div><b>${rupee(
      sum(
        S.stocks.filter((s) => s.location === 'Outlet'),
        (s) => s.quantity * (product(s.product_id)?.cost || 0),
      ),
    )}</b></div><div class="mix-item"><div class="mix-icon">☕</div><div><strong>Micro café</strong><small>${S.products.filter((p) => p.kind === 'recipe').length} menu items · ingredient tracking</small></div><button class="text-btn" onclick="navTo('cafe')">View menu →</button></div><div style="padding:10px 23px 22px"><div class="help" style="margin:0">${S.settings.gst_enabled ? 'GST billing is enabled. Prices include applicable tax.' : 'GST is available. Add your registration details in Settings to enable tax invoices.'}</div></div></div></div>
<div class="dashboard-grid"><div class="card"><div class="card-head"><h2>Recent invoices</h2><button class="text-btn" onclick="invoiceList()">View all →</button></div>${documentTable(S.documents.filter((d) => d.kind === 'sale').slice(0, 5))}</div><div class="card"><div class="card-head"><h2>Stock to watch</h2><button class="text-btn" onclick="navTo('inventory')">View stock →</button></div>${
      low.length
        ? low
            .slice(0, 5)
            .map(
              (p) =>
                `<div class="mix-item"><div class="mix-icon">${symbol(p.category)}</div><div><strong>${esc(p.name)}</strong><small>Reorder at ${qty(p.minimum)} ${esc(p.unit)}</small></div><span class="pill warn">${qty(p.stock)} left</span></div>`,
            )
            .join('')
        : empty('No low-stock alerts right now.')
    }</div></div>${!S.products.length ? '<div class="notice">Start with Settings, add products and opening warehouse stock, then transfer stock to the outlet. You can also load sample data from Settings to explore.</div>' : ''}`
  );
}
function stat(label, value, ico, foot) {
  return `<div class="stat"><div class="stat-top">${label}<span class="stat-icon">${ico}</span></div><div class="stat-value">${value}</div><div class="stat-foot">${foot}</div></div>`;
}
function chart(docs) {
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - 6 + i);
    const key = businessDay(d);
    return {
      label: d.toLocaleDateString('en-IN', { weekday: 'short' }),
      value: sum(
        docs.filter((s) => businessDay(s.date) === key),
        'total',
      ),
    };
  });
  const max = Math.max(...days.map((d) => d.value), 100);
  return `<div class="chart"><div class="chart-note">${rupee(sum(days, 'value'))} <span style="color:#9da491">in the last 7 days</span></div><svg viewBox="0 0 600 180" preserveAspectRatio="none">${[20, 65, 110, 155].map((y) => `<line x1="0" x2="600" y1="${y}" y2="${y}" stroke="#eef0e8" stroke-dasharray="4 5"/>`).join('')}${days.map((d, i) => `<rect x="${30 + i * 81}" y="${155 - (d.value / max) * 130}" width="37" height="${Math.max((d.value / max) * 130, 2)}" rx="4" fill="${i === 6 ? '#bc984f' : '#d7e3d3'}"><title>${d.label}: ${rupee(d.value)}</title></rect>`).join('')}</svg><div class="chart-labels">${days.map((d) => `<span>${d.label}</span>`).join('')}</div></div>`;
}
function documentTable(docs) {
  return table(
    ['Invoice', 'Customer / supplier', 'Amount', 'Status', ''],
    docs.map(
      (d) =>
        `<tr><td><strong>${esc(d.id)}</strong><small>${date(d.date)} · ${esc(d.location)}</small></td><td>${esc(party(d.party_id)?.name || 'Walk-in customer')}<small>${esc(d.payment)}</small></td><td>${rupee(d.total)}</td><td><span class="pill ${d.reversed ? 'red' : d.paid < d.total ? 'warn' : ''}">${d.reversed ? 'Reversed' : d.paid < d.total ? 'Part paid' : 'Paid'}</span></td><td><button class="text-btn" onclick="viewInvoice('${esc(d.id)}')">View →</button></td></tr>`,
    ),
  );
}
function billing() {
  const cats = ['All', 'Café menu', ...new Set(S.products.filter((p) => p.kind !== 'ingredient').map((p) => p.category))];
  return (
    heading(
      'POINT OF SALE',
      'Let’s make a sale.',
      'Quick billing for cold drinks, café favourites and everyday essentials.',
      `<button class="btn secondary" onclick="invoiceList()">▤ Invoice history</button>`,
    ) +
    `<div class="pos-layout"><div><div class="toolbar"><div class="search" style="width:100%"><input id="product-search" placeholder="Search product or scan barcode…  F3" value="${esc(query)}"></div></div><div class="tabs">${cats.map((c) => `<button class="${category === c ? 'active' : ''}" data-category="${esc(c)}">${esc(c)}</button>`).join('')}</div><div id="product-results">${productCards()}</div><div class="help">F3: Search / scan · F5: Customer · F6: Quantity · F7: Discount · F8: Checkout<br>Stock is deducted from ${esc(localLocation())}. ${S.settings.node_mode === 'unified' ? 'Every node can bill and manage stock according to staff permissions.' : S.settings.admin_device_id ? (isMainPC() ? 'This PC sells the unallocated balance.' : 'This till sells only its assigned stock allowance.') : 'Assign and pair this PC in Settings before live use.'} Cases convert to the pack quantity.</div></div><div class="card cart"><div class="cart-head"><h2>Current bill <span style="float:right;font-size:10px;color:#9a9f93">${esc(localLocation())}</span></h2><div style="display:flex;gap:6px;margin-bottom:8px"><input id="customer-mobile" type="tel" placeholder="Customer mobile (optional)"><button class="btn secondary small" onclick="findCustomerMobile()">Find</button><button class="btn secondary small" onclick="billCustomerForm()">Search · F5</button></div><select id="sale-party" onchange="window.saleParty=this.value;window.priceTier=party(this.value)?.price_tier||'retail';refreshCart();refreshProducts()"><option value="">Walk-in customer</option>${selectOptions(
      S.parties.filter((p) => p.kind === 'customer'),
      window.saleParty,
    )}</select><select id="price-tier" aria-label="Selling price tier" style="margin-top:8px" onchange="window.priceTier=this.value;refreshCart();refreshProducts()"><option value="retail" ${window.priceTier !== 'wholesale' ? 'selected' : ''}>Retail price</option><option value="wholesale" ${window.priceTier === 'wholesale' ? 'selected' : ''}>Wholesale price</option></select></div><div id="cart-items">${cartRows()}</div><div class="cart-totals"><div class="total-row"><span>Subtotal</span><span id="subtotal">${rupee(cartTotal())}</span></div><div class="total-row"><span>Discount ₹</span><input id="discount" type="number" min="0" step="0.01" value="${window.saleDiscount || 0}" style="width:100px;padding:7px" oninput="window.saleDiscount=this.value;updateTotal()"></div><div class="total-row grand"><span>Total</span><span id="grand-total">${rupee(Math.max(0, cartTotal() - Math.round((window.saleDiscount || 0) * 100)))}</span></div><p style="font-size:10px">${S.settings.gst_enabled ? 'GST and applicable cess included' : 'GST not collected · registration not enabled'}</p></div><div class="cart-pay"><button class="btn gold" onclick="checkout()" ${!cart.length ? 'disabled' : ''}>Checkout & save bill <small>F8</small></button><button class="text-btn" style="width:100%;margin-top:13px" onclick="clearCart()">Clear bill</button></div></div></div>`
  );
}
function productCards() {
  const products = matchingProducts().filter(
    (p) =>
      p.kind !== 'ingredient' &&
      p.price > 0 &&
      (category === 'All' || (category === 'Café menu' && p.kind === 'recipe') || p.category === category),
  );
  posOffset = Math.min(posOffset, Math.max(0, Math.floor((products.length - 1) / PAGE_SIZE) * PAGE_SIZE));
  productViewState = S;
  productViewQuery = query;
  productViewCategory = category;
  productViewTier = window.priceTier;
  productViewOffset = posOffset;
  return products.length
    ? `<div class="product-grid">${products
        .slice(posOffset, posOffset + PAGE_SIZE)
        .map(
          (p) =>
            `<button class="product-card" data-product-id="${p.id}" onclick="addCart(${p.id})"><span class="product-symbol">${symbol(p.category)}</span><strong>${esc(p.name)}</strong><small>${p.kind === 'recipe' ? 'Made fresh' : qty(billStock(p.id)) + ' ' + esc(p.unit) + ' available'}</small><b>${rupee(salePrice(p))}</b></button>`,
        )
        .join('')}</div>` + pageControls(posOffset, products.length, PAGE_SIZE, 'moveProductPage')
    : empty('No matching products. Add products in Inventory.');
}
function refreshProducts() {
  clearTimeout(productSearchTimer);
  const host = $('#product-results');
  if (!host) return;
  if (
    productViewHost === host &&
    productViewState === S &&
    productViewQuery === query &&
    productViewCategory === category &&
    productViewTier === window.priceTier &&
    productViewOffset === posOffset
  )
    return;
  host.innerHTML = productCards();
  productViewHost = host;
}
function moveProductPage(direction) {
  const old = posOffset;
  posOffset = Math.max(0, posOffset + direction * PAGE_SIZE);
  refreshProducts();
  if (old !== posOffset) $('#product-results .product-card')?.focus();
}
function salePrice(p) {
  return window.priceTier === 'wholesale' && p.wholesale_price > 0 ? p.wholesale_price : p.price;
}
function isMainPC() {
  return !S.settings.device_location || S.settings.device_id === S.settings.admin_device_id;
}
function billStock(id, loc = localLocation()) {
  if (S.settings.node_mode === 'unified' || !S.settings.admin_device_id) return stock(id, loc);
  if (isMainPC())
    return Math.max(
      0,
      stock(id, loc) -
        sum(
          S.allocations.filter((a) => a.product_id == id && a.location === loc),
          'quantity',
        ),
    );
  return S.allocations.find((a) => a.device_id === S.settings.device_id && a.product_id == id && a.location === loc)?.quantity || 0;
}
function cartTotal() {
  return sum(cart, (l) => Math.round(salePrice(product(l.id)) * l.quantity));
}
function cartLine(l) {
  const p = product(l.id);
  return `<div class="cart-line" data-product-id="${p.id}"><div class="cart-line-top"><strong>${esc(p.name)}</strong><span data-line-total>${rupee(salePrice(p) * l.quantity)}</span></div><div class="cart-line-bottom"><div class="qty-control"><button data-minus aria-label="Decrease ${esc(p.name)} quantity" onclick="changeQty(${l.id},${l.quantity - 1})">−</button><input required data-cart-quantity data-kb-key="quantity-${l.id}" aria-label="${esc(p.name)} quantity" type="number" min="0" step="any" value="${l.quantity}" onchange="changeQty(${l.id},this.value)"><button data-plus aria-label="Increase ${esc(p.name)} quantity" onclick="changeQty(${l.id},${l.quantity + 1})">＋</button></div><small>${esc(p.unit)} ${p.pack > 1 ? `<button class="text-btn" data-case onclick="changeQty(${l.id},${l.quantity + p.pack})">＋ case (${qty(p.pack)})</button>` : ''}</small></div></div>`;
}
function cartRows() {
  return cart.length
    ? `<div class="cart-items">${cart.map(cartLine).join('')}</div>`
    : empty('Your bill is empty.<br>Choose a product or scan a barcode.');
}
function refreshCart() {
  if (page !== 'billing' || !$('#cart-items')) return render();
  const host = $('#cart-items');
  let list = host.querySelector('.cart-items');
  if (!cart.length) {
    host.innerHTML = cartRows();
    activeCartId = null;
  } else {
    if (!list) {
      host.innerHTML = '<div class="cart-items"></div>';
      list = host.firstElementChild;
    }
    const current = new Map([...list.querySelectorAll('.cart-line')].map((el) => [Number(el.dataset.productId), el]));
    for (const l of cart) {
      let row = current.get(l.id);
      if (!row) {
        list.insertAdjacentHTML('beforeend', cartLine(l));
        continue;
      }
      current.delete(l.id);
      row.querySelector('[data-cart-quantity]').value = l.quantity;
      row.querySelector('[data-line-total]').textContent = rupee(salePrice(product(l.id)) * l.quantity);
      row.querySelector('[data-minus]').setAttribute('onclick', `changeQty(${l.id},${l.quantity - 1})`);
      row.querySelector('[data-plus]').setAttribute('onclick', `changeQty(${l.id},${l.quantity + 1})`);
      row.querySelector('[data-case]')?.setAttribute('onclick', `changeQty(${l.id},${l.quantity + product(l.id).pack})`);
    }
    for (const row of current.values()) row.remove();
  }
  $('#subtotal').textContent = rupee(cartTotal());
  updateTotal();
  $('.cart-pay .btn.gold').disabled = !cart.length;
  if (draftLoaded) saveBillDraft();
}
function addCart(id) {
  if (window.saleTradeOrder) return toast('This basket belongs to a WhatsApp order. Clear it to start a separate sale.', true);
  const p = product(id);
  if (!p) return toast('Product unavailable. Refresh the catalogue.', true);
  if (p.price <= 0) return toast('Set a selling price in Inventory first.', true);
  const l = cart.find((l) => l.id === id);
  if (p.kind !== 'recipe' && (l?.quantity || 0) + 1 > billStock(id))
    return toast('Quantity exceeds available stock at this location.', true);
  if (l) l.quantity++;
  else cart.push({ id, quantity: 1 });
  activeCartId = id;
  refreshCart();
  return true;
}
function changeQty(id, n) {
  const line = cart.find((l) => l.id === id),
    input = $(`[data-product-id="${id}"] [data-cart-quantity]`);
  if (!line) return false;
  const reject = (message) => {
    if (input) {
      input.value = line.quantity;
      input.focus();
      input.select();
    }
    toast(message, true);
    return false;
  };
  if (window.saleTradeOrder) return reject('Review quantities on the WhatsApp order before billing.');
  const raw = n;
  n = Number(n);
  if (raw === '' || !Number.isFinite(n) || n < 0) return reject('Enter a valid nonnegative quantity.');
  if (product(id).kind !== 'recipe' && n > billStock(id)) return reject('Quantity exceeds available stock at this location.');
  const removedFocused = !n && input === document.activeElement;
  if (n === 0) cart = cart.filter((l) => l.id !== id);
  else line.quantity = n;
  activeCartId = n ? id : cart.at(-1)?.id;
  refreshCart();
  if (removedFocused) $('#product-search')?.focus();
  return true;
}
function clearCart() {
  window.saleTradeOrder = '';
  cart = [];
  window.saleDiscount = 0;
  if ($('#discount')) $('#discount').value = 0;
  refreshCart();
}
function updateTotal() {
  $('#grand-total').textContent = rupee(Math.max(0, cartTotal() - Math.round((Number(window.saleDiscount) || 0) * 100)));
  if (draftLoaded) saveBillDraft();
}
function openModal(title, body, footer = '') {
  const d = $('#modal');
  $('#modal-body').innerHTML =
    `<div class="modal-head"><h2>${title}</h2><button onclick="closeModal()" aria-label="Close">×</button></div><div class="modal-content"><div id="form-error" class="error" role="alert"></div>${body}</div>${footer ? `<div class="modal-footer">${footer}</div>` : ''}`;
  if (!d.open) d.showModal();
}
function closeModal() {
  $('#modal').close();
}
function field(label, name, value = '', type = 'text', extra = '') {
  return `<div class="field"><label for="f-${name}">${label}</label><input id="f-${name}" name="${name}" type="${type}" value="${esc(value)}" ${extra}></div>`;
}
function dropdown(label, name, options, value) {
  return `<div class="field"><label for="f-${name}">${label}</label><select id="f-${name}" name="${name}">${options
    .map((o) => {
      const v = typeof o === 'string' ? o : o.value,
        n = typeof o === 'string' ? o : o.label;
      return `<option value="${esc(v)}" ${String(v) === String(value) ? 'selected' : ''}>${esc(n)}</option>`;
    })
    .join('')}</select></div>`;
}
function formModal(title, body, onSubmit, button = 'Save') {
  openModal(
    title,
    `<form id="edit-form">${body}<button type="submit" hidden></button></form>`,
    `<button class="btn secondary" onclick="closeModal()">Cancel</button><button class="btn gold" id="form-submit" onclick="document.getElementById('edit-form').requestSubmit()">${button}</button><small class="entry-hint">Enter: next field · Shift+Enter: previous · Ctrl+Enter: save</small>`,
  );
  $('#edit-form').onsubmit = async (e) => {
    e.preventDefault();
    if ($('#form-submit').disabled) return;
    $('#form-error').textContent = '';
    $('#form-submit').disabled = true;
    try {
      const data = Object.fromEntries(new FormData(e.target));
      await onSubmit(data);
      if ($('#edit-form') === e.target) closeModal();
    } catch (err) {
      $('#form-error').textContent = err.message;
    } finally {
      if ($('#form-submit')) $('#form-submit').disabled = false;
    }
  };
}
function checkout() {
  if (!cart.length) return;
  const discount = Number(window.saleDiscount || 0);
  if (!Number.isFinite(discount) || discount < 0) {
    $('#discount').focus();
    return toast('Enter a valid nonnegative discount.', true);
  }
  for (const input of document.querySelectorAll('[data-cart-quantity]')) {
    if (!input.reportValidity()) return;
    if (!changeQty(Number(input.closest('.cart-line').dataset.productId), input.value)) return;
  }
  if (!cart.length) return;
  const total = cartTotal() - Math.round(discount * 100);
  if (total < 0) return toast('Discount exceeds total.', true);
  formModal(
    'Complete sale',
    `<div class="report-number">${rupee(total)}</div><div class="entry-hint">Alt+C Cash · Alt+U UPI · Alt+D Card · Alt+B Bank · Ctrl+Enter Save</div><p>${esc(party(window.saleParty)?.name || 'Walk-in customer')} · ${esc(localLocation())}</p><div class="help">Save the bill before collecting or printing. UPI and card entries record payment; they do not charge the customer.</div><div class="form-grid">${dropdown('Payment method', 'payment', ['Cash', 'UPI', 'Card', 'Bank'], 'Cash')}${field('Amount received ₹', 'paid', total / 100, 'number', 'min="0" step="0.01" required')}${field('Place of supply (state code)', 'supply_state', party(window.saleParty)?.gstin?.slice(0, 2) || S.settings.state, 'text', 'pattern="[0-9]{2}" maxlength="2"')}${field('Reference / note', 'reference')}${dropdown('Second payment method (split)', 'payment2', [{ value: '', label: 'None' }, 'Cash', 'UPI', 'Card', 'Bank'], '')}${field('Second amount ₹', 'paid2', '', 'number', 'min="0" step="0.01"')}</div><div id="checkout-upi"></div><small>For customer credit, select a customer and enter the amount received. Change is not counted as revenue.</small>`,
    async (data) => {
      if (data.payment2 && Number(data.paid2) > 0)
        data.payments = [
          { method: data.payment, amount: data.paid },
          { method: data.payment2, amount: data.paid2 },
        ];
      delete data.payment2;
      delete data.paid2;
      const r = await mutate('sale', {
        ...data,
        price_tier: window.priceTier || 'retail',
        party_id: window.saleParty || null,
        location: localLocation(),
        discount: window.saleDiscount || 0,
        trade_order_id: window.saleTradeOrder || '',
        items: cart.map((l) => ({ product_id: l.id, quantity: l.quantity })),
      });
      cart = [];
      saveBillDraft();
      window.saleTradeOrder = '';
      window.saleDiscount = 0;
      window.saleParty = '';
      window.priceTier = 'retail';
      render();
      closeModal();
      viewInvoice(r.id);
      toast('Sale saved. Stock and customer ledger updated.');
      if (S.settings.receipt_auto && S.settings.receipt_printer) directPrint('print_receipt', { id: r.id });
    },
    'Save invoice',
  );
  bindCheckoutUpi(total);
}
let invoiceKind = 'sale',
  invoiceQuery = '',
  invoiceOffset = 0;
function invoiceRows() {
  const docs = S.documents.filter(
    (d) => d.kind === invoiceKind && `${d.id} ${party(d.party_id)?.name || ''}`.toLowerCase().includes(invoiceQuery.toLowerCase()),
  );
  invoiceOffset = Math.min(invoiceOffset, Math.max(0, Math.floor((docs.length - 1) / RECORD_PAGE_SIZE) * RECORD_PAGE_SIZE));
  return (
    documentTable(docs.slice(invoiceOffset, invoiceOffset + RECORD_PAGE_SIZE)) +
    pageControls(invoiceOffset, docs.length, RECORD_PAGE_SIZE, 'moveInvoicePage')
  );
}
function moveInvoicePage(direction) {
  invoiceOffset = Math.max(0, invoiceOffset + direction * RECORD_PAGE_SIZE);
  $('#invoice-results').innerHTML = invoiceRows();
  $('#invoice-results tbody button')?.focus();
}
function invoiceList(kind = 'sale') {
  invoiceKind = kind;
  invoiceQuery = '';
  invoiceOffset = 0;
  openModal(
    kind === 'purchase' ? 'Purchase history' : 'Invoice history',
    `${historyNote()}<div class="search" style="margin-bottom:20px"><input id="invoice-search" placeholder="Find invoice or customer / supplier"></div><div id="invoice-results">${invoiceRows()}</div>`,
  );
  $('#invoice-search').oninput = (e) => {
    invoiceQuery = e.target.value;
    invoiceOffset = 0;
    $('#invoice-results').innerHTML = invoiceRows();
  };
}

function receiptHTML(d) {
  const snap = d.snapshot,
    shop = snap.shop,
    items = snap.items,
    gst = sum(items, 'gst_amount'),
    cess = sum(items, 'cess_amount');
  return `<div class="receipt-preview"><div class="receipt-shop"><h2>${esc(shop.name)}</h2><p>${esc(shop.address)}</p><small>${shop.phone ? 'Tel: ' + esc(shop.phone) + '<br>' : ''}${shop.gst_enabled ? 'GSTIN: ' + esc(shop.gstin) : shop.composition ? 'Composition taxable person, not eligible to collect tax on supplies' : 'GST not collected'}${shop.fssai ? '<br>FSSAI Lic. No. ' + esc(shop.fssai) : ''}</small><h3 style="margin:17px 0 4px">${d.reversed ? 'REVERSED · ' : ''}${docTitle(d)}</h3></div><p style="font-size:11px">No: <b>${esc(d.id)}</b><br>${date(d.date)} ${new Date(d.date).toLocaleTimeString('en-IN')} · ${esc(d.location)}<br>${snap.original_id ? 'Against: <b>' + esc(snap.original_id) + '</b> of ' + date(snap.original_date) + '<br>Reason: ' + esc(snap.reason) + '<br>' : ''}${d.kind.startsWith('purchase') ? 'Supplier' : 'Customer'}: ${esc(snap.party.name || 'Walk-in customer')}${snap.party.gstin ? '<br>GSTIN: ' + esc(snap.party.gstin) : ''}${snap.party.address ? '<br>' + esc(snap.party.address) : ''}<br>Place of supply: ${esc(snap.supply_state)} ${shop.gst_enabled ? '· ' + esc(snap.tax_type) : ''}</p>${table(
    ['Item', 'Qty', 'Rate', 'Total'],
    items.map(
      (i) =>
        `<tr><td>${esc(i.name)}<small>${i.hsn ? 'HSN/SAC ' + esc(i.hsn) : ''}${shop.gst_enabled ? ' · GST ' + i.gst + '%' + (i.cess ? ' / Cess ' + i.cess + '%' : '') : ''}</small></td><td>${qty(i.quantity)} ${esc(i.unit)}</td><td>${rupee(i.price)}</td><td>${rupee(i.total)}</td></tr>`,
    ),
  )}${isNote(d) ? '' : `<div class="total-row"><span>Discount included</span><span>${rupee(d.discount)}</span></div>`}${shop.gst_enabled ? `<div class="total-row"><span>Taxable value</span><span>${rupee(d.total - d.tax - (snap.round_off || 0))}</span></div>${snap.tax_type === 'IGST' ? `<div class="total-row"><span>IGST</span><span>${rupee(gst)}</span></div>` : `<div class="total-row"><span>CGST</span><span>${rupee(sum(items, 'cgst_amount'))}</span></div><div class="total-row"><span>SGST</span><span>${rupee(sum(items, 'sgst_amount'))}</span></div>`}${cess ? `<div class="total-row"><span>Cess</span><span>${rupee(cess)}</span></div>` : ''}` : ''}${snap.round_off ? `<div class="total-row"><span>Round off</span><span>${snap.round_off > 0 ? '+' : '−'}${rupee(Math.abs(snap.round_off))}</span></div>` : ''}<div class="total-row grand"><span>${isNote(d) ? 'Value returned' : 'Total'}</span><span>${rupee(d.total)}</span></div>${tenderRows(d)}${upiBlock(d)}${d.reference ? `<p style="font-size:10px">Reference: ${esc(d.reference)}</p>` : ''}<p style="text-align:center;font-size:11px;margin-top:24px">Thank you for shopping with us.<br>Chill · Refresh · Enjoy · Always</p><p style="text-align:center;font-size:9px;margin-top:7px">Authorised signatory: __________________</p></div>`;
}
function viewInvoice(id) {
  const d = S.documents.find((d) => d.id === id);
  if (!d) {
    if (S.history && !S.history.complete)
      loadOlder().then(() => {
        if (S.documents.some((x) => x.id === id)) viewInvoice(id);
      });
    return;
  }
  openModal(
    docHeading(d),
    receiptHTML(d) + linkedNotes(d),
    `${!isNote(d) && !d.reversed && canOperate('return') ? `<button class="btn secondary small" onclick="returnForm('${esc(id)}')">Return items</button>` : ''}${!isNote(d) && !d.reversed && canOperate('reverse') && !notesFor(d.id).length ? `<button class="btn danger small" onclick="reverseDocument('${esc(id)}')">Reverse full ${d.kind === 'sale' ? 'bill' : 'purchase'}</button>` : ''}<button class="btn secondary" onclick="closeModal()">Close</button><button class="btn gold" onclick="printInvoice('${esc(id)}')">Print / Save PDF · F10</button>`,
  );
  $('#modal').dataset.invoiceId = id;
}
function printInvoice(id) {
  $('#print-area').innerHTML = receiptHTML(S.documents.find((d) => d.id === id));
  let st = $('#print-format');
  if (!st) {
    st = document.createElement('style');
    st.id = 'print-format';
    document.head.appendChild(st);
  }
  const width = S.settings.printer;
  st.textContent =
    width === 'A4'
      ? '@media print{#print-area{max-width:190mm;margin:auto}}'
      : `@media print{#print-area{width:${width === '58' ? '48' : '70'}mm;margin:0}#print-area .receipt-preview td{font-size:9px}} @page{size:${width}mm auto;margin:4mm}`;
  window.print();
}
function reverseDocument(id) {
  const d = S.documents.find((d) => d.id === id);
  formModal(
    'Reverse full document',
    `<div class="help">This restores the original stock movements and reverses outstanding credit. ${rupee(d.paid)} paid by ${esc(d.payment)} must be refunded or reconciled outside the app. This is a full internal reversal; a statutory GST credit note is not generated.</div>${field('Reason', 'reason', '', 'text', 'required')}`,
    async (data) => {
      const r = await mutate('reverse', { id, ...data }, 'Document reversed. Refund to reconcile: ' + rupee(d.paid));
      return r;
    },
    'Reverse document',
  );
}
