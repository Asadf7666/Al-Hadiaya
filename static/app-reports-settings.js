/* Reports, expenses, settings, sync, backup, imports and exports. */
let reportFrom = '',
  reportTo = '';
function reportDocuments() {
  return liveDocs().filter((d) => (!reportFrom || d.date.slice(0, 10) >= reportFrom) && (!reportTo || d.date.slice(0, 10) <= reportTo));
}
function reports() {
  const docs = reportDocuments(),
    sales = docs.filter((d) => d.kind === 'sale'),
    purchases = docs.filter((d) => d.kind === 'purchase'),
    cost =
      sum(
        sales.flatMap((d) => d.snapshot.items),
        'cost',
      ) -
      sum(
        docs.filter((d) => d.kind === 'sale_return' && d.snapshot.restocked).flatMap((d) => d.snapshot.items),
        'cost',
      ),
    expenses = S.expenses.filter(
      (e) => (!reportFrom || e.date.slice(0, 10) >= reportFrom) && (!reportTo || e.date.slice(0, 10) <= reportTo),
    ),
    returnDocs = docs.filter((d) => d.kind === 'sale_return'),
    revenue = sum(sales, (d) => d.total - d.tax) - sum(returnDocs, (d) => d.total - d.tax),
    gstLines = sales.flatMap((d) => d.snapshot.items.map((i) => ({ ...i, doc: d })));
  return (
    heading(
      'BUSINESS REPORTS',
      'Know where you stand.',
      'Sales, purchases, operating expenses and tax records in one place.',
      `<button class="btn secondary" onclick="exportSales()">↓ Sales CSV</button><button class="btn" onclick="expenseForm()">＋ Record expense</button>`,
    ) +
    `<div class="toolbar"><p style="font-size:12px">Reports include saved, unreversed transactions.</p><div class="range"><input id="report-from" type="date" value="${reportFrom}"><span>to</span><input id="report-to" type="date" value="${reportTo}"><button class="btn secondary small" onclick="applyReportRange()">Apply</button></div></div><div class="stats">${stat('Sales (including GST)', rupee(sum(sales, 'total') - sum(returnDocs, 'total')), '₹', sales.length + ' invoices' + (returnDocs.length ? ' · ' + rupee(sum(returnDocs, 'total')) + ' returned' : ' in selected period'))}${stat('Purchases', rupee(sum(purchases, 'total')), '↓', 'Recorded purchase invoice value')}${stat('Operating expenses', rupee(sum(expenses, 'amount')), '↗', expenses.length + ' expense entries')}${stat('Estimated contribution', rupee(revenue - cost - sum(expenses, 'amount')), '◴', 'Sales ex tax − recorded cost − expenses')}</div><div class="help">Contribution is a management estimate, not statutory profit. Recorded costs include purchase taxes; café ITC eligibility and formal accounting are not inferred. For GST filing, have your accountant review the exported sales records.</div><div class="dashboard-grid"><div class="card"><div class="card-head"><h2>GST sales summary</h2><button class="text-btn" onclick="exportGST()">Export details →</button></div>${table(
      ['Tax category', 'Taxable value', 'GST', 'Cess'],
      [...new Set(gstLines.map((l) => l.gst + '|' + l.cess + '|' + l.doc.snapshot.tax_type))].map((k) => {
        const ls = gstLines.filter((l) => l.gst + '|' + l.cess + '|' + l.doc.snapshot.tax_type === k);
        return `<tr><td>${ls[0].gst}% · ${esc(ls[0].doc.snapshot.tax_type)}${ls[0].cess ? ' + ' + ls[0].cess + '% cess' : ''}</td><td>${rupee(sum(ls, 'taxable'))}</td><td>${rupee(sum(ls, 'gst_amount'))}</td><td>${rupee(sum(ls, 'cess_amount'))}</td></tr>`;
      }),
    )}</div><div class="card"><div class="card-head"><h2>Expenses</h2></div>${table(
      ['Date', 'Expense', 'Amount'],
      expenses.map(
        (e) => `<tr><td>${date(e.date)}</td><td>${esc(e.name)}<small>${esc(e.method)}</small></td><td>${rupee(e.amount)}</td></tr>`,
      ),
    )}</div></div><div class="card"><div class="card-head"><h2>Payment methods at invoice issue</h2></div>${table(
      ['Method', 'Sales received', 'Purchases paid'],
      ['Cash', 'UPI', 'Card', 'Bank'].map(
        (m) =>
          `<tr><td>${m}</td><td>${rupee(
            sum(
              sales.filter((d) => d.payment === m),
              'paid',
            ),
          )}</td><td>${rupee(
            sum(
              purchases.filter((d) => d.payment === m),
              'paid',
            ),
          )}</td></tr>`,
      ),
    )}</div>`
  );
}
function expenseForm() {
  formModal(
    'Record shop expense',
    `${field('Expense description', 'name', '', 'text', 'required')}<div class="form-grid">${field('Amount ₹', 'amount', '', 'number', 'min="0.01" step="0.01" required')}${dropdown('Paid by', 'method', ['Cash', 'UPI', 'Card', 'Bank'], 'Cash')}</div>`,
    (data) => mutate('expense', data, 'Expense recorded.'),
  );
}
function settings() {
  const s = S.settings;
  return (
    heading(
      'YOUR SHOP, EVERYWHERE',
      'Your business on this node.',
      'Every PC has the same functions. Location selects where a transaction takes place.',
    ) +
    `<form id="settings-form"><div class="settings-layout"><div class="card"><div class="card-head"><h2>Business & GST</h2></div><div class="card-content"><div class="form-grid">${field('Business name', 'name', s.name, 'text', 'required')}${field('Phone', 'phone', s.phone, 'tel')}${field('Business address', 'address', s.address)}${field('GSTIN', 'gstin', s.gstin, 'text', 'maxlength="15"')}${field('State code (Karnataka = 29)', 'state', s.state, 'text', 'pattern="[0-9]{2}" maxlength="2" required')}${field('Invoice prefix', 'invoice_prefix', s.invoice_prefix, 'text', 'pattern="[A-Z0-9]{1,2}" maxlength="2" required')}</div><label class="check"><input type="checkbox" name="gst_enabled" ${s.gst_enabled ? 'checked' : ''}> Enable regular-registration GST</label><label class="check"><input type="checkbox" name="composition" ${s.composition ? 'checked' : ''}> Composition dealer (issue bill of supply)</label><label class="check"><input type="checkbox" name="round_off" ${s.round_off ? 'checked' : ''}> Round bills to the nearest rupee</label><div class="form-grid">${field('FSSAI licence no. (food sellers)', 'fssai', s.fssai || '', 'text', 'pattern="[0-9]{14}" maxlength="14" inputmode="numeric"')}${field('UPI ID for receipt QR', 'upi_id', s.upi_id || '', 'text', 'placeholder="name@bank"')}</div><div class="help">Verify GST classification with your accountant. Statutory credit notes, composition billing, IRN, e-way bills and portal filing are not included.</div>${dropdown(
      'Print layout',
      'printer',
      [
        { value: '80', label: '80 mm thermal receipt' },
        { value: '58', label: '58 mm thermal receipt' },
        { value: 'A4', label: 'A4 invoice' },
      ],
      s.printer,
    )}</div></div><div class="card"><div class="card-head"><h2>This node & sync</h2></div><div class="card-content"><div class="notice">Purchases, payments, stock, catalogue, café recipes, credit bills and business settings are available on every node, including offline. Sync exchanges saved changes. Competing offline stock or ledger transactions can require reconciliation; review any sync errors.</div>${field('PC name', 'device_name', s.device_name)}${dropdown('Default transaction location', 'device_location', ['Warehouse', 'Outlet'], s.device_location || 'Warehouse')}${s.cloud_url ? `<p>Connected to ${esc(s.cloud_url)}</p><button type="button" class="btn secondary small" onclick="serverAddressForm()">Update server address</button><button type="button" class="btn secondary small" onclick="disconnectServerForm()">Finish sync & disconnect server</button><button type="button" class="btn danger small" onclick="retireServerForm()">Server permanently removed?</button>` : `<button type="button" class="btn gold" onclick="cloudPairForm()">Connect to online business</button>${s.cloud_business_id ? '<button type="button" class="btn secondary small" onclick="serverAddressForm()">Resume existing server connection</button>' : ''}${field('Shared sync folder (alternative to server)', 'sync_folder', s.sync_folder, 'text', 'placeholder="C:\\Users\\Owner\\OneDrive\\AlHidayaShared"')}`}<div style="margin-top:15px">${field('Additional backup folder (optional)', 'backup_folder', s.backup_folder)}</div><p style="font-size:11px">Last exchange: ${s.last_sync ? esc(new Date(s.last_sync).toLocaleString()) : 'Not yet'}<br>Last verified backup: ${s.last_backup ? esc(new Date(s.last_backup).toLocaleString()) : 'Not yet'}<br>Automatic exchange every 30 seconds while the launcher is open.</p><div class="actions"><button type="button" class="btn secondary small" onclick="runSync()">↻ Sync now</button><button type="button" class="btn secondary small" onclick="runBackup()">Back up now</button><a class="btn secondary small" href="/api/backup-download" download="AlHidaya-backup.sqlite3">Download database</a><a class="btn secondary small" href="/api/backup-bundle" download>Download backup with photos</a><button type="button" class="btn secondary small" onclick="restoreForm()">Restore backup</button></div></div></div></div><div id="settings-error" class="error"></div><div class="actions" style="margin-top:20px"><button type="submit" class="btn gold">Save settings</button><button type="button" class="btn secondary" onclick="closeApp()">Close app safely</button>${!S.products.length ? '<button type="button" class="btn secondary" onclick="loadDemo()">Explore sample shop</button>' : ''}</div></form>${
      S.sync_errors.length
        ? `<div class="card" style="margin-top:22px"><div class="card-head"><h2>Sync needs review</h2></div>${table(
            ['Transaction', 'Issue'],
            S.sync_errors.map((e) => `<tr><td>${esc(e.id)}</td><td style="white-space:normal">${esc(e.message)}</td></tr>`),
          )}</div>`
        : ''
    }`
  );
}
function bindPage() {
  if (page === 'people')
    $('#people-search').oninput = (e) => {
      peopleQuery = e.target.value;
      peopleOffset = 0;
      $('#people-results').innerHTML = peoplePageRows();
    };
  if (page === 'billing') {
    productViewHost = $('#product-results');
    if ($('#product-search')) {
      $('#product-search').oninput = (e) => {
        query = e.target.value;
        posOffset = 0;
        clearTimeout(productSearchTimer);
        const field = e.target;
        productSearchTimer = setTimeout(() => {
          if (page === 'billing' && field === $('#product-search')) refreshProducts();
        }, 60);
      };
      $('#product-search').onkeydown = (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const p = scanProduct(e.target.value);
          if (p && p.kind !== 'ingredient') {
            if (addCart(p.id)) {
              query = '';
              posOffset = 0;
              e.target.value = '';
              refreshProducts();
            }
            e.target.focus();
          } else
            toast(
              p === null
                ? 'Code matches multiple products. Correct SKUs/barcodes in Inventory.'
                : 'Barcode not found. Add the manufacturer’s barcode in Inventory.',
              true,
            );
        }
      };
    }
    document.querySelectorAll('[data-category]').forEach(
      (b) =>
        (b.onclick = () => {
          category = b.dataset.category;
          posOffset = 0;
          refreshProducts();
          document.querySelectorAll('[data-category]').forEach((t) => t.classList.toggle('active', t === b));
        }),
    );
  }
  if (page === 'inventory')
    $('#inventory-search').oninput = (e) => {
      query = e.target.value;
      inventoryOffset = 0;
      refreshInventory();
    };
  if (page === 'settings')
    $('#settings-form').onsubmit = async (e) => {
      e.preventDefault();
      const button = e.target.querySelector('[type=submit]');
      if (button.disabled) return;
      button.disabled = true;
      try {
        const data = Object.fromEntries(new FormData(e.target));
        data.gst_enabled = e.target.gst_enabled.checked;
        if (e.target.composition) {
          data.composition = e.target.composition.checked;
          data.round_off = e.target.round_off.checked;
        }
        if (e.target.drawer_kick) {
          data.drawer_kick = e.target.drawer_kick.checked;
          data.receipt_auto = e.target.receipt_auto.checked;
        }
        await mutate('settings', data, 'Settings saved.');
      } catch (err) {
        $('#settings-error').textContent = err.message;
      } finally {
        button.disabled = false;
      }
    };
}
async function runSync() {
  try {
    const r = await mutate('sync');
    toast(r.message, r.pending > 0);
  } catch (e) {
    toast(e.message, true);
  }
}
async function runBackup() {
  try {
    const r = await mutate('backup');
    toast(r.message);
  } catch (e) {
    toast(e.message, true);
  }
}
function loadDemo() {
  formModal(
    'Explore sample data',
    `<div class="help">This adds sample stock, suppliers and café recipes. The database will be marked as a sample shop. For real trading, start with a separate empty data folder.</div>`,
    async () => {
      await mutate('demo', {}, 'Sample shop loaded.');
      navTo('overview');
    },
    'Load sample shop',
  );
}
function loadCatalogue() {
  formModal(
    'Add Indian starter catalogue',
    `<p>379 editable templates covering major beverage brands, common pack sizes, snacks, dairy, ice cream and café ingredients.</p><div class="help">These are product templates, not a current manufacturer catalogue. Availability and packaging vary by market. Existing SKUs stay as entered. New records start with zero stock and price, blank barcodes and unconfirmed tax rates. Scan real packs and enter your supplier’s details before trading.</div>`,
    async () => {
      const r = await mutate('catalog');
      toast(r.count + ' new product templates added.');
    },
    'Add catalogue',
  );
}
function parseCSV(text) {
  text = text.replace(/^\ufeff/, '');
  let rows = [],
    row = [],
    cell = '',
    quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else quoted = !quoted;
    } else if (c === ',' && !quoted) {
      row.push(cell);
      cell = '';
    } else if ((c === '\n' || c === '\r') && !quoted) {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(cell);
      if (row.some((v) => v.trim())) rows.push(row);
      row = [];
      cell = '';
    } else cell += c;
  }
  if (quoted) throw Error('CSV has an unclosed quoted field.');
  row.push(cell);
  if (row.some((v) => v.trim())) rows.push(row);
  const headers = rows.shift()?.map((h) => h.trim().toLowerCase());
  if (!headers?.includes('name') || !headers?.includes('sku')) throw Error('CSV must contain name and sku columns. Download the template.');
  return rows.map((r) => Object.fromEntries(headers.map((h, i) => [h, (r[i] || '').trim()]).filter(([h, v]) => v !== '')));
}
function importForm() {
  formModal(
    'Import products from CSV',
    `<p style="margin-bottom:18px">Import up to 1,000 rows at a time. Matching SKUs update product details; new SKUs create products. Existing stock is preserved.</p><button type="button" class="btn secondary small" onclick="downloadImportTemplate()">↓ Download CSV template</button><div class="field" style="margin-top:20px"><label for="import-file">Product CSV file</label><input id="import-file" type="file" accept=".csv,text/csv" required></div><div class="help">Required: name, sku, category and unit. Supported: barcode, brand, size, packaging, kind, price, cost, mrp, wholesale_price, gst, cess, hsn, tax_verified, pack, minimum, expiry, opening_stock and location. Price/cost values are rupees. Use tax_verified=true only after checking classification and rates. Opening stock is allowed only on new products.</div>`,
    async () => {
      const file = $('#import-file').files[0];
      if (!file) throw Error('Choose a CSV file.');
      if (file.size > 1000000) throw Error('CSV exceeds 1 MB.');
      const rows = parseCSV(await file.text());
      const r = await mutate('import_products', { rows });
      toast(r.count + ' products imported.');
    },
    'Import products',
  );
}
function downloadImportTemplate() {
  csv(
    'AlHidaya-product-import-template.csv',
    [
      'name',
      'sku',
      'barcode',
      'brand',
      'size',
      'packaging',
      'category',
      'unit',
      'kind',
      'price',
      'cost',
      'mrp',
      'wholesale_price',
      'gst',
      'cess',
      'hsn',
      'tax_verified',
      'pack',
      'minimum',
      'expiry',
      'opening_stock',
      'location',
    ],
    [
      [
        'Example beverage 250 ml',
        'MY-SKU-001',
        '',
        'Example brand',
        '250 ml',
        'PET bottle',
        'Cold drinks',
        'bottle',
        'stock',
        0,
        0,
        0,
        0,
        0,
        0,
        '',
        'false',
        24,
        12,
        '',
        0,
        'Warehouse',
      ],
    ],
  );
}
function closeApp() {
  formModal(
    'Close Al Hadiya Traders',
    `<p>A verified local backup will be created before the app closes. You can then close the browser tab or run a newer Setup.exe to update.</p>`,
    async () => {
      const r = await api('shutdown');
      closeModal();
      $('#main').innerHTML = heading('SESSION CLOSED', 'Shop data saved.', esc(r.message));
      toast(r.message);
    },
    'Back up & close',
  );
}
function csv(name, headers, rows) {
  const cell = (v) => {
    let s = String(v ?? '');
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
    return '"' + s.replace(/"/g, '""') + '"';
  };
  const blob = new Blob(['\ufeff' + [headers, ...rows].map((r) => r.map(cell).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' }),
    a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function exportStock() {
  csv(
    'AlHidaya-stock.csv',
    [
      'SKU',
      'Product',
      'Unit',
      'Warehouse',
      'Outlet',
      'Total stock',
      'Selling price',
      'Recorded cost',
      'GST %',
      'Cess %',
      'Lots and expiry',
    ],
    S.products.map((p) => [
      p.sku,
      p.name,
      p.unit,
      stock(p.id, 'Warehouse'),
      stock(p.id, 'Outlet'),
      p.stock,
      p.price / 100,
      p.cost / 100,
      p.gst,
      p.cess,
      productLots(p.id)
        .filter((l) => l.expiry)
        .map((l) => `${l.location} ${l.lot || 'no lot no.'} ${l.expiry} x${qty(l.quantity)}`)
        .join('; '),
    ]),
  );
}
function exportSales() {
  csv(
    'AlHidaya-sales.csv',
    ['Invoice', 'Date', 'Location', 'Customer', 'Total', 'Tax', 'Paid at issue', 'Payment', 'Discount'],
    reportDocuments()
      .filter((d) => d.kind === 'sale')
      .map((d) => [
        d.id,
        d.date,
        d.location,
        d.snapshot.party.name || 'Walk-in',
        d.total / 100,
        d.tax / 100,
        d.paid / 100,
        d.payment,
        d.discount / 100,
      ]),
  );
}
function exportGST() {
  csv(
    'AlHidaya-GST-sales.csv',
    [
      'Invoice',
      'Date',
      'Customer GSTIN',
      'Place of supply',
      'HSN/SAC',
      'Product',
      'Quantity',
      'GST rate',
      'Cess rate',
      'Taxable value',
      'CGST',
      'SGST',
      'IGST',
      'Cess',
      'Total',
    ],
    reportDocuments()
      .filter((d) => d.kind === 'sale')
      .flatMap((d) =>
        d.snapshot.items.map((i) => {
          const igst = d.snapshot.tax_type === 'IGST';
          return [
            d.id,
            d.date,
            d.snapshot.party.gstin || '',
            d.snapshot.supply_state,
            i.hsn,
            i.name,
            i.quantity,
            i.gst,
            i.cess,
            i.taxable / 100,
            (i.cgst_amount || 0) / 100,
            (i.sgst_amount || 0) / 100,
            igst ? i.gst_amount / 100 : 0,
            i.cess_amount / 100,
            i.total / 100,
          ];
        }),
      ),
  );
}
function tick() {
  $('#clock').textContent =
    new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) +
    ' · ' +
    new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}
