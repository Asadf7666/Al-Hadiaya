/* Inventory, products, transfers, adjustments and movement history. */
function inventory() {
  const locs = ['All', 'Warehouse', 'Outlet'],
    filtered = matchingProducts();
  return (
    heading(
      'STOCK CONTROL',
      'Every bottle accounted for.',
      'Track packaged products and café ingredients at both locations.',
      `<button class="btn secondary" onclick="transferForm()">⇄ Stock transfer</button><button class="btn" onclick="productForm()">＋ Add product</button>`,
    ) +
    `<div class="toolbar"><div class="search"><input id="inventory-search" placeholder="Search name or barcode…" value="${esc(query)}"></div><div class="actions"><button class="btn secondary small" onclick="adjustForm()">Adjust / wastage</button><button class="btn secondary small" onclick="movementList()">Movement history</button><button class="btn secondary small" onclick="importForm()">Import CSV</button><button class="btn secondary small" onclick="loadCatalogue()">Starter catalogue</button><button class="btn secondary small" onclick="exportStock()">Export CSV</button></div></div><div class="tabs">${locs.map((l) => `<button class="${stockFilter === l ? 'active' : ''}" onclick="stockFilter='${l}';render()">${l === 'All' ? 'Both locations' : l}</button>`).join('')}</div><div class="card" id="inventory-results">${inventoryPageRows(filtered)}</div><div class="help">One base unit per product: bottles, packs, ml or grams. Cases convert to the configured number of base units. Each delivery can carry its own lot number and expiry. Sales use the earliest-expiring lot first and never an expired one.</div>`
  );
}
function inventoryTable(products) {
  return table(
    ['Product', 'Category', 'Warehouse', 'Outlet', 'Selling price', 'GST / cess', 'Stock status', ''],
    products.map((p) => {
      const count = stockFilter === 'All' ? p.stock : stock(p.id, stockFilter);
      return `<tr><td><strong>${esc(p.name)}</strong><small>${esc(p.sku)}${p.barcode ? ' · ▥ ' + esc(p.barcode) : ''} · ${p.kind === 'recipe' ? 'Made fresh' : esc(p.unit)}${lotNote(p.id)}</small></td><td>${esc(p.category)}</td><td>${p.kind === 'recipe' ? '—' : qty(stock(p.id, 'Warehouse'))}</td><td>${p.kind === 'recipe' ? 'Made fresh' : qty(stock(p.id, 'Outlet'))}</td><td>${rupee(p.price)}</td><td>${p.gst}%${p.cess ? ' + ' + p.cess + '%' : ''}</td><td><span class="pill ${p.kind !== 'recipe' && count <= p.minimum ? 'warn' : ''}">${p.kind === 'recipe' ? 'Made fresh' : !p.price && !p.cost && !p.stock ? 'Needs setup' : count <= p.minimum ? 'Low stock' : 'In stock'}</span>${lotPill(p.id)}</td><td>${productLots(p.id).length ? `<button class="text-btn" onclick="lotList(${p.id})">Lots</button>` : ''}<button class="text-btn" onclick="productForm(${p.id})">Edit</button></td></tr>`;
    }),
  );
}
function productForm(id, cafeItem = false) {
  const p = id
    ? product(id)
    : {
        category: cafeItem ? 'Coffee' : 'Cold drinks',
        unit: cafeItem ? 'cup' : 'bottle',
        kind: cafeItem ? 'recipe' : 'stock',
        price: 0,
        cost: 0,
        gst: 0,
        cess: 0,
        minimum: cafeItem ? 0 : 12,
        pack: cafeItem ? 1 : 24,
      };
  const categories = [
    'Cold drinks',
    'Packaged water',
    'Juices',
    'Energy drinks',
    'Ice cream',
    'Snacks',
    'Tea & coffee',
    'Dairy & milk',
    'Mojitos',
    'Coffee',
    'Ingredients',
  ];
  if (!categories.includes(p.category)) categories.push(p.category);
  formModal(
    id ? 'Edit product' : 'Add product',
    `<div class="form-grid">${field('Product name', 'name', p.name, 'text', 'required')}${field('Internal SKU', 'sku', p.sku, 'text', 'required')}${field('Manufacturer barcode (scan pack)', 'barcode', p.barcode)}${field('Brand', 'brand', p.brand)}${field('Pack size', 'size', p.size, 'text', 'list="size-presets"')}${field('Packaging', 'packaging', p.packaging, 'text', 'list="pack-presets"')}${field('MRP ₹ (0 if not applicable)', 'mrp', (p.mrp || 0) / 100, 'number', 'min="0" step="0.01"')}${field('Wholesale price ₹ per base unit', 'wholesale_price', (p.wholesale_price || 0) / 100, 'number', 'min="0" step="0.01"')}${dropdown('Category', 'category', categories, p.category)}${dropdown(
      'Product type',
      'kind',
      [
        { value: 'stock', label: 'Packaged stock' },
        { value: 'ingredient', label: 'Café ingredient' },
        { value: 'recipe', label: 'Café menu item (made fresh)' },
      ],
      p.kind,
    )}${field('Base unit (bottle, ml, g, cup)', 'unit', p.unit, 'text', 'required')}${field('Base units per case / pack', 'pack', p.pack, 'number', 'min="1" step="any" required')}${field('Selling price ₹ (tax inclusive)', 'price', p.price / 100, 'number', 'min="0" step="0.01" required')}${field('Purchase cost ₹ per base unit', 'cost', p.cost / 100, 'number', 'min="0" step="0.01" required')}${field('GST rate %', 'gst', p.gst, 'number', 'min="0" max="100" step="any"')}${field('Cess rate % (if applicable)', 'cess', p.cess, 'number', 'min="0" max="100" step="any"')}${field('HSN / SAC', 'hsn', p.hsn)}${field('Low-stock threshold', 'minimum', p.minimum, 'number', 'min="0" step="any"')}${!id ? field('Opening stock in base units', 'stock', 0, 'number', 'min="0" step="any"') + dropdown('Opening stock location', 'location', ['Warehouse', 'Outlet'], 'Warehouse') + field('Opening stock lot / batch no. (optional)', 'lot', '', 'text', 'maxlength="40"') + field('Opening stock expiry (optional)', 'expiry', '', 'date') : ''}</div><datalist id="size-presets">${['100 ml', '150 ml', '160 ml', '180 ml', '200 ml', '250 ml', '300 ml', '330 ml', '350 ml', '400 ml', '450 ml', '473 ml', '500 ml', '600 ml', '650 ml', '750 ml', '1 L', '1.2 L', '1.25 L', '1.5 L', '1.75 L', '2 L', '2.25 L', '3 L', '5 L', '10 L', '20 L', '25 g', '50 g', '75 g', '100 g', '150 g', '200 g', '250 g', '500 g', '1 kg', '2 kg', '5 kg', 'Small pack', 'Regular pack'].map((v) => `<option value="${v}">`).join('')}</datalist><datalist id="pack-presets">${['PET bottle', 'Glass bottle', 'Can', 'Carton', 'Cup', 'Sachet', 'Pack', 'Tub', 'Jar', 'Case', 'Crate'].map((v) => `<option value="${v}">`).join('')}</datalist><label class="check"><input type="checkbox" name="tax_verified" ${p.tax_verified ? 'checked' : ''}> HSN/SAC and tax rate have been checked for this product</label><div class="help">Rates depend on classification and registration. Use current supplier invoices and your accountant’s advice. Café ingredients must use the same units as the recipe.</div>`,
    (data) => mutate('product', { ...data, id: id || null }, id ? 'Product updated.' : 'Product added.'),
  );
}
function transferForm() {
  formModal(
    'Transfer stock between locations',
    `${dropdown(
      'Product',
      'product_id',
      S.products.filter((p) => p.kind !== 'recipe').map((p) => ({ value: p.id, label: p.name })),
    )}<div class="form-grid">${dropdown('Dispatch from', 'source', ['Warehouse', 'Outlet'], S.settings.device_location || 'Warehouse')}${dropdown('Send to', 'target', ['Warehouse', 'Outlet'], S.settings.device_location === 'Outlet' ? 'Warehouse' : 'Outlet')}${field('Quantity in base units', 'quantity', '', 'number', 'min="0.001" step="any" required')}${field('Transfer note', 'note', 'Stock transfer')}${lotPicker('Lot to send')}</div><div class="help">Stock leaves the source and is allocated to the destination. The receiving PC sees it after sync. Only dispatch goods you have actually sent.</div>`,
    (data) => mutate('transfer', data, 'Transfer saved. Sync both PCs to exchange the stock movement.'),
  );
  bindLotPicker('source');
}
function adjustForm() {
  formModal(
    'Stock adjustment / wastage',
    `${dropdown(
      'Product',
      'product_id',
      S.products.filter((p) => p.kind !== 'recipe').map((p) => ({ value: p.id, label: p.name })),
    )}${dropdown('Location', 'location', ['Warehouse', 'Outlet'], localLocation())}${field('Quantity change (negative for wastage)', 'quantity', '', 'number', 'step="any" required')}${field('Reason', 'note', '', 'text', 'required')}<div class="form-grid">${lotPicker('Lot to reduce (wastage)')}${field('Lot / batch no. when adding stock', 'lot', '', 'text', 'maxlength="40"')}${field('Expiry when adding stock', 'expiry', '', 'date')}</div><div class="help">Examples: −2 bottles damaged, +3 bottles found during stock count. Wastage clears the oldest dates first unless you pick a lot.</div>`,
    (data) => mutate('adjust', data, 'Stock adjustment recorded.'),
  );
  bindLotPicker('location');
}
function movementList() {
  openModal(
    'Recent stock movements',
    table(
      ['Date', 'Product', 'Location', 'Change', 'Reason'],
      S.movements.map(
        (m) =>
          `<tr><td>${date(m.date)}<small>${esc(m.reference)}</small></td><td>${esc(product(m.product_id)?.name)}</td><td>${esc(m.location)}</td><td style="color:${m.quantity < 0 ? '#a06e57' : '#527558'}">${m.quantity > 0 ? '+' : ''}${qty(m.quantity)}</td><td>${esc(m.note)}</td></tr>`,
      ),
    ),
  );
}
