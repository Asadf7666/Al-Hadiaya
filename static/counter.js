/* Counter and cash features: returns with credit and debit notes, split payments,
   UPI QR, cashier shifts with day close, stock count, credit ageing and HSN summary. */
const NOTE_KINDS = { sale_return: 'CREDIT NOTE', purchase_return: 'DEBIT NOTE' };
function isNote(d) {
  return d.kind in NOTE_KINDS;
}
function notesFor(id) {
  return S.documents.filter((d) => isNote(d) && d.reference === id);
}
function docTitle(d) {
  const shop = d.snapshot.shop;
  return (
    NOTE_KINDS[d.kind] ||
    (d.kind === 'purchase' ? 'PURCHASE RECORD' : shop.gst_enabled ? 'TAX INVOICE' : shop.composition ? 'BILL OF SUPPLY' : 'SALE RECEIPT')
  );
}
function docHeading(d) {
  return d.kind === 'sale'
    ? 'Invoice details'
    : d.kind === 'purchase'
      ? 'Purchase record'
      : d.kind === 'sale_return'
        ? 'Credit note'
        : 'Debit note';
}
function tenders(d) {
  return d.snapshot.payments || (d.paid ? [{ method: d.payment, amount: d.paid }] : []);
}
function tenderRows(d) {
  const row = (label, amount) => `<div class="total-row"><span>${label}</span><span>${rupee(amount)}</span></div>`;
  if (isNote(d))
    return (
      tenders(d)
        .map((t) => row((d.kind === 'sale_return' ? 'Refunded · ' : 'Received back · ') + esc(t.method), t.amount))
        .join('') + (d.snapshot.credit ? row('Adjusted against amount owed', d.snapshot.credit) : '')
    );
  return (
    (tenders(d)
      .map((t) => row('Paid · ' + esc(t.method), t.amount))
      .join('') || row('Paid', 0)) + row('Credit at issue', d.total - d.paid)
  );
}
function upiLink(shop, amount, note) {
  return `upi://pay?pa=${encodeURIComponent(shop.upi_id)}&pn=${encodeURIComponent(shop.name)}&am=${(amount / 100).toFixed(2)}&cu=INR&tn=${encodeURIComponent(note)}`;
}
function upiSvg(text) {
  try {
    const q = qrcode(0, 'M');
    q.addData(text);
    q.make();
    return q.createSvgTag({ cellSize: 3, margin: 6, scalable: true });
  } catch {
    return '';
  }
}
function upiBlock(d) {
  const shop = d.snapshot.shop;
  if (d.kind !== 'sale' || d.reversed || !shop.upi_id) return '';
  const due = d.total - d.paid,
    viaUpi = tenders(d)
      .filter((t) => t.method === 'UPI')
      .reduce((n, t) => n + t.amount, 0),
    amount = due > 0 ? due : viaUpi;
  if (!amount) return '';
  return `<div class="upi-block"><div class="upi-qr">${upiSvg(upiLink(shop, amount, d.id))}</div><p><b>Scan to pay ${rupee(amount)}</b><br>${esc(shop.upi_id)}<br><small>Any UPI app. Check the payee name before paying.</small></p></div>`;
}
function bindCheckoutUpi(total) {
  const host = $('#checkout-upi'),
    s = S.settings;
  if (!host || !s.upi_id) return;
  const draw = () => {
    const first = $('#f-payment').value === 'UPI' ? Math.round(Number($('#f-paid').value || 0) * 100) : 0,
      second = $('#f-payment2').value === 'UPI' ? Math.round(Number($('#f-paid2').value || 0) * 100) : 0,
      amount = first + second;
    host.innerHTML =
      amount > 0
        ? `<div class="upi-block"><div class="upi-qr">${upiSvg(upiLink(s, amount, 'Bill'))}</div><p><b>Customer scans to pay ${rupee(amount)}</b><br>${esc(s.upi_id)}<br><small>Confirm the money arrived before saving the bill.</small></p></div>`
        : '';
  };
  ['f-payment', 'f-paid', 'f-payment2', 'f-paid2'].forEach((id) => $('#' + id)?.addEventListener('input', draw));
  draw();
}
function linkedNotes(d) {
  const notes = notesFor(d.id);
  if (!notes.length) return '';
  return `<div class="linked-notes"><h3>Returns against this ${d.kind === 'sale' ? 'bill' : 'purchase'}</h3>${notes.map((n) => `<div class="total-row"><span>${esc(n.id)} · ${date(n.date)}</span><span>${rupee(n.total)} <button class="text-btn" onclick="viewInvoice('${esc(n.id)}')">View →</button></span></div>`).join('')}</div>`;
}
function returnedQty(d) {
  const done = {};
  notesFor(d.id).forEach((n) => n.snapshot.items.forEach((i) => (done[i.line] = (done[i.line] || 0) + i.quantity)));
  return done;
}
function returnForm(id) {
  const d = S.documents.find((x) => x.id === id),
    done = returnedQty(d),
    sale = d.kind === 'sale';
  const rows = d.snapshot.items.map((i, n) => {
    const left = Number((i.quantity - (done[n] || 0)).toFixed(6));
    return `<tr><td>${esc(i.name)}<small>Billed ${qty(i.quantity)} · ${rupee(Math.round(i.total / i.quantity))} each after discount</small></td><td>${qty(left)} ${esc(i.unit)}</td><td><input class="return-qty" data-line="${n}" data-each="${i.total / i.quantity}" type="number" min="0" max="${left}" step="any" value="0" aria-label="Quantity of ${esc(i.name)} to return" ${left ? '' : 'disabled'}></td></tr>`;
  });
  formModal(
    sale ? 'Return items · credit note' : 'Return to supplier · debit note',
    `${table(['Item', 'Left to return', 'Return now'], rows)}<div class="form-grid" style="margin-top:18px">${field('Reason', 'reason', '', 'text', 'required')}${dropdown(sale ? 'Refund method' : 'Money received back by', 'payment', ['Cash', 'UPI', 'Card', 'Bank'], 'Cash')}</div>${sale ? '<label class="check"><input type="checkbox" name="restock" checked> Put the goods back into stock</label>' : ''}<div class="help" id="return-total">Enter the quantity coming back for each item.</div>`,
    async (data) => {
      const items = [...document.querySelectorAll('.return-qty')]
        .filter((e) => Number(e.value) > 0)
        .map((e) => ({ line: Number(e.dataset.line), quantity: e.value }));
      if (!items.length) throw Error('Enter a quantity for at least one item.');
      const r = await mutate('return', {
        id,
        reason: data.reason,
        payment: data.payment,
        restock: sale ? $('#edit-form').restock.checked : true,
        items,
      });
      closeModal();
      viewInvoice(r.id);
      toast(
        (sale ? 'Credit note ' : 'Debit note ') +
          r.id +
          ' saved.' +
          (r.refund ? ' Refund ' + rupee(r.refund) + ' by ' + r.method + '.' : '') +
          (r.credit ? ' ' + rupee(r.credit) + ' taken off the amount owed.' : ''),
      );
    },
    sale ? 'Save credit note' : 'Save debit note',
  );
  const total = () => {
    const value = [...document.querySelectorAll('.return-qty')].reduce(
      (n, e) => n + Math.round(Number(e.value || 0) * Number(e.dataset.each)),
      0,
    );
    $('#return-total').textContent = value
      ? `Value returned: ${rupee(value)}. Any amount still owed on this ${sale ? 'bill' : 'purchase'} is cancelled first; the rest is refunded.`
      : 'Enter the quantity coming back for each item.';
  };
  document.querySelectorAll('.return-qty').forEach((e) => e.addEventListener('input', total));
}
/* Shifts and day close */
function shiftCard() {
  const sh = S.shift,
    can = canOperate('shift_open');
  if (!sh)
    return `<div class="card shift-card"><div class="card-head"><h2>Cash drawer</h2><span class="pill">No shift open</span></div><div class="card-content"><div class="licence-summary"><span>Open a shift with the cash in the drawer to get a day-end report.</span>${can ? '<button class="btn secondary" onclick="shiftOpenForm()">Open shift</button>' : ''}</div>${S.shifts.length ? `<button class="text-btn" onclick="shiftHistory()">Past day-end reports →</button>` : ''}</div></div>`;
  const m = sh.summary;
  return `<div class="card shift-card"><div class="card-head"><h2>Cash drawer</h2><span class="pill warn">Shift open since ${new Date(sh.opened).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span></div><div class="card-content"><div class="shift-figures"><div><small>Cash expected in drawer</small><b>${rupee(m.expected_cash)}</b></div><div><small>Sales this shift</small><b>${rupee(m.sales_total)}</b></div><div><small>UPI received</small><b>${rupee(m.methods.UPI.in)}</b></div><div><small>Opening float</small><b>${rupee(m.opening_float)}</b></div></div><div class="licence-actions">${can ? '<button class="btn gold" onclick="shiftCloseForm()">Count cash and close day</button>' : ''}${S.settings.receipt_printer && S.settings.drawer_kick ? '<button class="btn secondary" onclick="directPrint(\'open_drawer\',{})">Open drawer</button>' : ''}${S.shifts.length ? '<button class="btn secondary" onclick="shiftHistory()">Past reports</button>' : ''}</div></div></div>`;
}
function shiftOpenForm() {
  formModal(
    'Open shift',
    field('Cash in the drawer now ₹ (opening float)', 'opening_float', 0, 'number', 'min="0" step="0.01" required'),
    async (data) => {
      await mutate('shift_open', data, 'Shift opened.');
      closeModal();
    },
    'Open shift',
  );
}
function shiftCloseForm() {
  const m = S.shift.summary;
  formModal(
    'Count cash and close day',
    `<div class="report-number">${rupee(m.expected_cash)}</div><p>Cash the records say should be in the drawer.</p><div class="form-grid" style="margin-top:16px">${field('Cash counted in the drawer ₹', 'counted', '', 'number', 'min="0" step="0.01" required')}${field('Note (optional)', 'note')}</div><div class="help" id="shift-difference">Count the notes and coins, then enter the total.</div>`,
    async (data) => {
      const r = await mutate('shift_close', data);
      closeModal();
      shiftReport(S.shifts.find((s) => s.id === r.id));
    },
    'Close shift',
  );
  $('#f-counted').addEventListener('input', (e) => {
    const diff = Math.round(Number(e.target.value || 0) * 100) - m.expected_cash;
    $('#shift-difference').textContent =
      diff === 0
        ? 'The drawer matches the records.'
        : diff > 0
          ? `Drawer is over by ${rupee(diff)}.`
          : `Drawer is short by ${rupee(-diff)}.`;
  });
}
function shiftReportHTML(sh) {
  const m = sh.summary,
    row = (a, b, cls = '') => `<div class="total-row ${cls}"><span>${a}</span><span>${b}</span></div>`;
  return (
    `<div class="receipt-preview"><div class="receipt-shop"><h2>${esc(S.settings.name)}</h2><h3 style="margin:12px 0 4px">DAY-END REPORT</h3></div><p style="font-size:11px">Opened: ${date(sh.opened)} ${new Date(sh.opened).toLocaleTimeString('en-IN')} by ${esc(sh.opened_by)}<br>Closed: ${date(sh.closed)} ${new Date(sh.closed).toLocaleTimeString('en-IN')} by ${esc(sh.closed_by)}</p>` +
    row(`Sales (${m.sales} bills)`, rupee(m.sales_total)) +
    row(`Returns (${m.returns} credit notes)`, '−' + rupee(m.returns_total)) +
    row('Sold on credit', rupee(m.credit_given)) +
    row('Collected from customers', rupee(m.collections)) +
    row('Paid to suppliers', rupee(m.supplier_payments)) +
    row('Expenses', rupee(m.expenses)) +
    ['Cash', 'UPI', 'Card', 'Bank'].map((k) => row(`${k} in / out`, `${rupee(m.methods[k].in)} / ${rupee(m.methods[k].out)}`)).join('') +
    row('Opening float', rupee(m.opening_float)) +
    row('Cash expected', rupee(m.expected_cash), 'grand') +
    row('Cash counted', rupee(m.counted_cash)) +
    row(m.difference === 0 ? 'Difference' : m.difference > 0 ? 'Over' : 'Short', rupee(Math.abs(m.difference))) +
    (sh.note ? `<p style="font-size:10px">Note: ${esc(sh.note)}</p>` : '') +
    `<p style="text-align:center;font-size:9px;margin-top:14px">Cashier: __________  Owner: __________</p></div>`
  );
}
function shiftReport(sh) {
  openModal(
    'Day-end report',
    shiftReportHTML(sh),
    `<button class="btn secondary" onclick="closeModal()">Close</button><button class="btn gold" onclick="printShift(${sh.id})">Print / Save PDF</button>`,
  );
}
function printShift(id) {
  if (S.settings.receipt_printer) return directPrint('print_shift', { id });
  $('#print-area').innerHTML = shiftReportHTML(S.shifts.find((s) => s.id === id));
  window.print();
}
function shiftHistory() {
  openModal(
    'Past day-end reports',
    table(
      ['Closed', 'Cashier', 'Sales', 'Cash expected', 'Counted', 'Difference', ''],
      S.shifts.map(
        (s) =>
          `<tr><td>${date(s.closed)}<small>${new Date(s.closed).toLocaleTimeString('en-IN')}</small></td><td>${esc(s.closed_by)}</td><td>${rupee(s.summary.sales_total)}</td><td>${rupee(s.expected)}</td><td>${rupee(s.counted)}</td><td><span class="pill ${s.summary.difference ? 'warn' : ''}">${s.summary.difference === 0 ? 'Matched' : (s.summary.difference > 0 ? 'Over ' : 'Short ') + rupee(Math.abs(s.summary.difference))}</span></td><td><button class="text-btn" onclick="shiftReport(S.shifts.find(x=>x.id===${s.id}))">View →</button></td></tr>`,
      ),
    ),
    `<button class="btn secondary" onclick="closeModal()">Close</button>`,
  );
}
/* Stock count */
function stockCountForm() {
  const place = localLocation() === 'Outlet' ? 'Outlet' : 'Warehouse';
  formModal(
    'Stock count',
    `<div class="form-grid">${dropdown('Location counted', 'location', ['Warehouse', 'Outlet'], place)}${field('Note (for example: month end)', 'note')}</div><div class="search" style="margin:6px 0 12px"><input id="count-filter" placeholder="Filter products…" aria-label="Filter products"></div><div id="count-rows"></div><div class="help" id="count-summary">Type what is on the shelf. Rows you leave blank are not changed.</div>`,
    async (data) => {
      const counts = [...document.querySelectorAll('.count-input')]
        .filter((e) => e.value !== '')
        .map((e) => ({ product_id: Number(e.dataset.id), counted: e.value }));
      if (!counts.length) throw Error('Enter a counted quantity for at least one product.');
      const r = await mutate('stock_count', { location: data.location, note: data.note, counts });
      closeModal();
      toast(r.adjusted ? `Stock count saved. ${r.adjusted} of ${r.counted} products adjusted.` : 'Stock count saved. Everything matched.');
    },
    'Post differences',
  );
  const entered = {},
    draw = () => {
      const loc = $('#f-location').value,
        term = $('#count-filter').value.toLowerCase();
      $('#count-rows').innerHTML = table(
        ['Product', 'In records', 'Counted', 'Difference'],
        S.products
          .filter((p) => p.kind !== 'recipe' && (p.name + ' ' + p.sku + ' ' + (p.barcode || '')).toLowerCase().includes(term))
          .slice(0, 200)
          .map((p) => {
            const held = stock(p.id, loc),
              v = entered[p.id] ?? '';
            return `<tr><td>${esc(p.name)}<small>${esc(p.sku)}</small></td><td>${qty(held)} ${esc(p.unit)}</td><td><input class="count-input" data-id="${p.id}" data-held="${held}" type="number" min="0" step="any" value="${v}" aria-label="Counted ${esc(p.name)}"></td><td class="count-diff">${v === '' ? '—' : qty(Number(v) - held)}</td></tr>`;
          }),
      );
      document.querySelectorAll('.count-input').forEach((e) =>
        e.addEventListener('input', () => {
          entered[e.dataset.id] = e.value;
          e.closest('tr').querySelector('.count-diff').textContent = e.value === '' ? '—' : qty(Number(e.value) - Number(e.dataset.held));
          const changed = Object.entries(entered).filter(([, x]) => x !== '').length;
          $('#count-summary').textContent = changed
            ? `${changed} product${changed > 1 ? 's' : ''} counted. Only differences are posted, with the oldest dates cleared first.`
            : 'Type what is on the shelf. Rows you leave blank are not changed.';
        }),
      );
    };
  $('#f-location').addEventListener('change', () => {
    Object.keys(entered).forEach((k) => delete entered[k]);
    draw();
  });
  $('#count-filter').addEventListener('input', draw);
  draw();
}
/* Reports: notes, credit ageing, HSN summary */
function creditAgeing() {
  const now = Date.now(),
    rows = [];
  S.parties
    .filter((p) => p.kind === 'customer' && p.balance > 0)
    .forEach((p) => {
      let left = p.balance;
      const b = [0, 0, 0, 0];
      S.documents
        .filter((d) => d.party_id === p.id && d.kind === 'sale' && !d.reversed && d.total > d.paid)
        .sort((x, y) => y.date.localeCompare(x.date))
        .forEach((d) => {
          const take = Math.min(left, d.total - d.paid);
          if (take <= 0) return;
          left -= take;
          const age = Math.floor((now - new Date(d.date)) / 864e5);
          b[age <= 30 ? 0 : age <= 60 ? 1 : age <= 90 ? 2 : 3] += take;
        });
      if (left > 0) b[3] += left;
      rows.push({ p, b });
    });
  return rows.sort((x, y) => y.p.balance - x.p.balance);
}
function exportAgeing() {
  csv(
    'AlHidaya-credit-ageing.csv',
    ['Customer', 'Phone', 'Total owed', '0-30 days', '31-60 days', '61-90 days', 'Over 90 days'],
    creditAgeing().map(({ p, b }) => [p.name, p.phone, p.balance / 100, ...b.map((n) => n / 100)]),
  );
}
function hsnSummary() {
  const groups = {};
  reportDocuments()
    .filter((d) => d.kind === 'sale' || d.kind === 'sale_return')
    .forEach((d) => {
      const sign = d.kind === 'sale' ? 1 : -1;
      d.snapshot.items.forEach((i) => {
        const k = (i.hsn || '') + '|' + i.gst + '|' + i.cess,
          g =
            groups[k] ||
            (groups[k] = {
              hsn: i.hsn || '',
              gst: i.gst,
              cess: i.cess,
              unit: i.unit,
              quantity: 0,
              taxable: 0,
              cgst: 0,
              sgst: 0,
              igst: 0,
              cessAmount: 0,
              total: 0,
            });
        g.quantity += sign * i.quantity;
        g.taxable += sign * (i.taxable ?? i.total);
        g.cgst += sign * (i.cgst_amount || 0);
        g.sgst += sign * (i.sgst_amount || 0);
        g.igst += sign * (i.igst_amount || 0);
        g.cessAmount += sign * (i.cess_amount || 0);
        g.total += sign * i.total;
      });
    });
  return Object.values(groups).sort((a, b) => a.hsn.localeCompare(b.hsn));
}
function exportHsn() {
  csv(
    'AlHidaya-HSN-summary.csv',
    [
      'HSN/SAC',
      'UQC (unit)',
      'Total quantity',
      'GST rate %',
      'Cess rate %',
      'Taxable value',
      'CGST',
      'SGST',
      'IGST',
      'Cess',
      'Total value',
    ],
    hsnSummary().map((g) => [
      g.hsn,
      g.unit,
      Number(g.quantity.toFixed(3)),
      g.gst,
      g.cess,
      g.taxable / 100,
      g.cgst / 100,
      g.sgst / 100,
      g.igst / 100,
      g.cessAmount / 100,
      g.total / 100,
    ]),
  );
}
function exportNotes() {
  csv(
    'AlHidaya-credit-debit-notes.csv',
    ['Note', 'Type', 'Date', 'Against', 'Party', 'Party GSTIN', 'Value', 'Tax', 'Refunded', 'Adjusted against dues', 'Reason'],
    reportDocuments()
      .filter(isNote)
      .map((d) => [
        d.id,
        d.kind === 'sale_return' ? 'Credit note' : 'Debit note',
        d.date,
        d.reference,
        d.snapshot.party.name || 'Walk-in',
        d.snapshot.party.gstin || '',
        d.total / 100,
        d.tax / 100,
        d.paid / 100,
        (d.snapshot.credit || 0) / 100,
        d.snapshot.reason,
      ]),
  );
}
function reportExtras() {
  const notes = reportDocuments().filter(isNote),
    ageing = creditAgeing(),
    hsn = hsnSummary();
  return `<div class="dashboard-grid report-extras"><div class="card"><div class="card-head"><h2>Credit ageing</h2><button class="text-btn" onclick="exportAgeing()">Export →</button></div>${table(
    ['Customer', 'Owed', '0–30 days', '31–60', '61–90', 'Over 90'],
    ageing
      .slice(0, 12)
      .map(
        ({ p, b }) =>
          `<tr><td>${esc(p.name)}</td><td><strong>${rupee(p.balance)}</strong></td>${b.map((n, i) => `<td>${n ? `<span class="${i === 3 ? 'pill red' : i === 2 ? 'pill warn' : ''}">${rupee(n)}</span>` : '—'}</td>`).join('')}</tr>`,
      ),
  )}</div><div class="card"><div class="card-head"><h2>Credit and debit notes</h2><button class="text-btn" onclick="exportNotes()">Export →</button></div>${table(
    ['Note', 'Against', 'Value', ''],
    notes
      .slice(0, 12)
      .map(
        (d) =>
          `<tr><td><strong>${esc(d.id)}</strong><small>${d.kind === 'sale_return' ? 'Credit note' : 'Debit note'} · ${date(d.date)}</small></td><td>${esc(d.reference)}</td><td>${rupee(d.total)}</td><td><button class="text-btn" onclick="viewInvoice('${esc(d.id)}')">View →</button></td></tr>`,
      ),
  )}</div></div><div class="card report-extras" style="margin-bottom:24px"><div class="card-head"><h2>HSN summary of sales, net of returns</h2><button class="text-btn" onclick="exportHsn()">Export for GSTR-1 →</button></div>${table(
    ['HSN/SAC', 'Quantity', 'Rate', 'Taxable value', 'Tax', 'Total'],
    hsn
      .slice(0, 15)
      .map(
        (g) =>
          `<tr><td>${esc(g.hsn || 'Not set')}</td><td>${qty(g.quantity)} ${esc(g.unit)}</td><td>${g.gst}%${g.cess ? ' + ' + g.cess + '%' : ''}</td><td>${rupee(g.taxable)}</td><td>${rupee(g.cgst + g.sgst + g.igst + g.cessAmount)}</td><td>${rupee(g.total)}</td></tr>`,
      ),
  )}</div>`;
}
/* Direct receipt printing */
async function directPrint(action, data) {
  try {
    const r = await api(action, data);
    toast(action === 'open_drawer' ? 'Drawer opened.' : 'Sent to ' + r.printer + '.');
  } catch (e) {
    toast(e.message, true);
  }
}
const browserPrintInvoice = printInvoice;
printInvoice = function (id) {
  return S.settings.receipt_printer ? directPrint('print_receipt', { id, reprint: true }) : browserPrintInvoice(id);
};
function printerCard() {
  const s = S.settings,
    names = [...new Set([...(S.printers || []), ...(s.receipt_printer ? [s.receipt_printer] : [])])];
  return `<div class="card" id="printer-card"><div class="card-head"><h2>Receipt printer</h2>${s.receipt_printer ? '<button type="button" class="btn secondary small" onclick="directPrint(\'print_test\',{})">Print test</button>' : ''}</div><div class="card-content">${dropdown('Print bills on', 'receipt_printer', [{ value: '', label: 'Print dialog (choose each time)' }, ...names], s.receipt_printer || '')}${dropdown(
    'Paper',
    'receipt_columns',
    [
      { value: '32', label: '58 mm · 32 characters' },
      { value: '42', label: '80 mm · 42 characters' },
      { value: '48', label: '80 mm · 48 characters' },
    ],
    s.receipt_columns || '48',
  )}<label class="check"><input type="checkbox" name="receipt_auto" ${s.receipt_auto ? 'checked' : ''}> Print each bill as soon as it is saved</label><label class="check"><input type="checkbox" name="drawer_kick" ${s.drawer_kick ? 'checked' : ''}> Open the cash drawer on cash bills</label><div class="help">For thermal receipt printers that accept ESC/POS. Save settings, then use Print test. If the test prints garbled text, choose the print dialog instead.</div></div></div>`;
}
const counterRender = render;
render = function () {
  counterRender();
  if (!S) return;
  if (page === 'overview' && S.shifts) $('#main .page-heading')?.insertAdjacentHTML('afterend', shiftCard());
  if (page === 'settings' && S.local) $('.settings-layout')?.insertAdjacentHTML('beforeend', printerCard());
  if (page === 'reports') {
    $('#main .toolbar')?.insertAdjacentHTML('afterend', historyNote());
    $('#main').insertAdjacentHTML('beforeend', reportExtras());
  }
  if (page === 'inventory' && canOperate('stock_count'))
    $('#main .toolbar .actions')?.insertAdjacentHTML(
      'afterbegin',
      '<button class="btn secondary small" onclick="stockCountForm()">Stock count</button>',
    );
};
