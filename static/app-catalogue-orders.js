/* Photo catalogue, catalogue orders and WhatsApp trading orders. */
function imagePicker(label, name, value) {
  return `<div class="field"><label>${label}</label><select name="${esc(name)}" id="f-${esc(name)}" onchange="const p=document.getElementById('preview-${esc(name)}');p.src='/media/'+this.value;p.style.display=this.value?'block':'none'"><option value="">No image</option>${(S.media_assets || []).map((a) => `<option value="${esc(a.id)}" ${a.id === value ? 'selected' : ''}>${esc(a.name)}</option>`).join('')}</select><input type="file" accept="image/png,image/jpeg" onchange="uploadImage(this,'${esc(name)}')"><div class="help">JPEG or PNG, up to 5 MB. Upload a product photograph or campaign creative.</div><img id="preview-${esc(name)}" ${value ? 'src="/media/' + esc(value) + '"' : ''} style="max-width:180px;max-height:160px;border-radius:10px;${value ? '' : 'display:none'}"></div>`;
}
async function uploadImage(input, name) {
  const file = input.files[0];
  if (!file) return;
  try {
    if (file.size > 5000000) throw Error('Use an image under 5 MB.');
    const encoded = await new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result.split(',')[1]);
      r.onerror = reject;
      r.readAsDataURL(file);
    });
    const result = await api('media_upload', { name: file.name, content: encoded });
    const select = document.getElementById('f-' + name);
    const option = document.createElement('option');
    option.value = result.id;
    option.textContent = file.name;
    select.append(option);
    select.value = result.id;
    const preview = document.getElementById('preview-' + name);
    preview.src = '/media/' + result.id;
    preview.style.display = 'block';
    toast('Image uploaded.');
  } catch (e) {
    toast(e.message, true);
  }
}
function catalogueManagement() {
  const rows = S.catalogue_products || [],
    orders = S.catalogue_orders || [];
  return `<div class="card" style="margin-top:20px"><div class="card-head"><div><h2>Photo catalogue & order requests</h2><p>Publish chosen products with real photos and prices.</p></div><button class="text-btn" onclick="catalogueSettings()">Catalogue settings</button><button class="text-btn" onclick="catalogueProduct()">＋ Publish product</button></div><div class="help">${S.online ? `<a href="/catalogue" target="_blank">Open customer catalogue →</a>` : 'Publish on your hosted sender to make the catalogue available to customers.'} This shop catalogue works independently of Meta Commerce approval.</div>${table(
    ['Product', 'Photo', 'Published', ''],
    rows.map(
      (r) =>
        `<tr><td>${esc(product(r.product_id)?.name)}</td><td><img src="/media/${esc(r.asset_id)}" style="width:60px;height:60px;object-fit:cover;border-radius:8px"></td><td>${r.published ? 'Yes' : 'Draft'}</td><td><button class="text-btn" onclick="catalogueProduct(${r.product_id})">Edit</button></td></tr>`,
    ),
  )}<div class="card-head"><h2>Customer order requests</h2></div>${table(
    ['Request / customer', 'Estimated total', 'Status', ''],
    orders.map(
      (o) =>
        `<tr><td>${esc(o.id)}<small>${esc(o.name)} · +${esc(o.phone)}</small></td><td>${rupee(o.total)}</td><td>${esc(o.status)}</td><td><button class="text-btn" onclick="catalogueOrder('${esc(o.id)}')">Review</button></td></tr>`,
    ),
  )}</div>`;
}
function catalogueProduct(pid) {
  const r = (S.catalogue_products || []).find((r) => r.product_id === pid) || {};
  formModal(
    'Product photo & publication',
    `<label>Product<select name="product_id">${selectOptions(
      S.products.filter((p) => p.kind !== 'ingredient'),
      pid,
    )}</select></label>${imagePicker('Product photo', 'asset_id', r.asset_id || '')}${field('Description', 'description', r.description || '')}<label class="check"><input type="checkbox" name="published" ${r.published ? 'checked' : ''}> Publish in customer catalogue</label><label class="check"><input type="checkbox" name="policy_confirmed"> I checked this genuine food/non-alcoholic drink, accurate photo, price and description against the catalogue policy.</label><div class="help">A positive retail price and a photo are required. Recheck publication after changing the product or price. Unpublished inventory remains private.</div>`,
    (data) => mutate('catalogue_product', data, 'Catalogue product saved.'),
  );
}
function catalogueSettings() {
  formModal(
    'Customer catalogue',
    `<label class="check"><input type="checkbox" name="enabled" ${S.settings.catalogue_enabled ? 'checked' : ''}> Enable public catalogue</label>${field('Shop WhatsApp number (optional, public)', 'phone', S.settings.catalogue_phone || '', 'tel')}${imagePicker('Catalogue banner', 'banner', S.settings.catalogue_banner || '')}<div class="help">The number is shown publicly for shop enquiries. Order requests don’t take payment or reserve stock.</div>`,
    (data) => mutate('catalogue_settings', data, 'Catalogue settings saved.'),
  );
}
function catalogueOrder(id) {
  const o = (S.catalogue_orders || []).find((o) => o.id === id);
  if (!o) return;
  formModal(
    'Order request ' + esc(id),
    `<p>${esc(o.name)} · +${esc(o.phone)}</p><p>${JSON.parse(o.items)
      .map((i) => esc(i.name) + ' × ' + i.quantity)
      .join(
        '<br>',
      )}</p><p>${esc(o.note)}</p>${dropdown('Status', 'status', ['new', 'contacted', 'fulfilled', 'cancelled'], o.status)}<button type="button" class="btn secondary" onclick="catalogueToBill('${esc(id)}')">Prepare bill in POS</button><div class="help">Prices and stock are checked again at checkout. This request is not a saved invoice.</div>`,
    (data) => mutate('catalogue_order_status', { ...data, id }, 'Request status saved.'),
  );
}
function catalogueToBill(id) {
  window.saleTradeOrder = '';
  const o = S.catalogue_orders.find((o) => o.id === id);
  if (['fulfilled', 'cancelled'].includes(o.status)) return toast('Review the request status before preparing a bill.', true);
  window.saleDiscount = 0;
  const items = JSON.parse(o.items);
  if (items.some((i) => !product(i.id))) return toast('An item is no longer available. Review the order.', true);
  cart = items.map((i) => ({ id: i.id, quantity: i.quantity }));
  window.saleParty =
    S.parties.find((p) => p.kind === 'customer' && String(p.phone).replace(/\D/g, '').endsWith(o.phone.slice(-10)))?.id || '';
  window.priceTier = 'retail';
  closeModal();
  navTo('billing');
  toast('Order loaded. Confirm customer, availability and payment before saving the bill.');
}

function ordersPage() {
  const orders = S.trade_orders || [],
    maps = S.commerce_products || [],
    s = S.settings,
    owner = !S.online || S.web_user?.role === 'owner';
  return (
    heading(
      'WHATSAPP TRADING',
      'Orders from your customers.',
      'Customers browse the native WhatsApp catalogue, send a cart and receive order updates.',
      owner
        ? `<button class="btn secondary" onclick="commerceSettings()">Connect Meta catalogue</button><button class="btn" onclick="commerceMapping()">Map trading product</button>`
        : '',
    ) +
    `<div class="notice">${s.whatsapp_commerce_enabled ? 'Catalogue automation enabled.' : 'Native catalogue automation awaits setup.'} ${s.whatsapp_catalogue_id ? 'Catalogue ' + esc(s.whatsapp_catalogue_id) : 'No Meta catalogue ID saved.'} ${s.whatsapp_catalogue_checked ? 'Connection checked ' + date(s.whatsapp_catalogue_checked) : 'Save catalogue ID, check its Meta link, then enable automation.'}<br>Replies: MENU / SHOP opens catalogue · STATUS checks latest order · CANCEL WA-… requests cancellation. Orders use Warehouse stock. Confirmation does not reserve stock; invoicing checks it again.</div><div class="card" style="margin-top:20px">${table(
      ['Order / customer', 'Estimated total', 'Status / invoice', ''],
      orders.map(
        (o) =>
          `<tr><td>${esc(o.id)}<small>${esc(o.name)} · +${esc(o.phone)}</small></td><td>${rupee(o.total)}</td><td>${esc(o.status)}<small>${esc(o.invoice_id || 'Not invoiced')}</small></td><td><button class="text-btn" onclick="tradeOrder('${esc(o.id)}')">Manage</button></td></tr>`,
      ),
    )}</div>${
      owner
        ? `<div class="card" style="margin-top:20px"><div class="card-head"><h2>Meta retailer SKU mappings</h2>${S.online ? '<a class="btn secondary" href="/api/commerce-feed">Download Meta feed CSV</a>' : ''}</div>${table(
            ['Meta retailer ID', 'Product / pack', 'Price tier', ''],
            maps.map(
              (m) =>
                `<tr><td>${esc(m.retailer_id)}<small>Catalogue ${esc(m.catalog_id)}</small></td><td>${esc(product(m.product_id)?.name)}<small>${m.units} base units per catalogue item</small></td><td>${esc(m.price_tier)} · ${m.active ? 'Active' : 'Disabled'}</td><td><button class="text-btn" onclick="commerceMapping(${m.id})">Edit</button></td></tr>`,
            ),
          )}<div class="help">Publish photos and confirmed prices in Photo catalogue first, map each Meta retailer ID to a trading product, then upload the exported CSV in Commerce Manager. Feed includes only mapped, published, priced trading products. Once connected and enabled, configure Commerce Manager to fetch <a href="/commerce-feed.csv" target="_blank">the scheduled feed URL</a> hourly for automatic price and availability updates. Case packs and single bottles can have separate retailer IDs.</div></div>`
        : ''
    }`
  );
}
function commerceSettings() {
  const s = S.settings;
  formModal(
    'Native WhatsApp catalogue',
    `${field('Owned Meta Commerce catalogue ID', 'catalog_id', s.whatsapp_catalogue_id)}${field('Approved order-update utility template', 'order_template', s.whatsapp_order_template)}<label class="check"><input type="checkbox" name="reply" ${s.whatsapp_catalogue_reply ? 'checked' : ''}> Reply automatically to MENU / CATALOGUE / SHOP</label><label class="check"><input type="checkbox" name="enabled" ${s.whatsapp_commerce_enabled ? 'checked' : ''}> Enable native catalogue and order automation</label><div class="help">In Meta Commerce Manager create/select your trading catalogue and connect it to this WhatsApp Business Account. Save its ID first, then check the connection below. Enable only after successful check and webhook subscription.</div><button type="button" class="btn secondary" onclick="checkCommerce()">Check connection & enable Meta cart</button>`,
    (data) => mutate('commerce_settings', data, 'Catalogue settings saved.'),
  );
}
async function checkCommerce() {
  try {
    await api('commerce_check');
    await load();
    toast('Catalogue linked; native cart and visibility enabled. Save automation settings.');
  } catch (e) {
    toast(e.message, true);
  }
}
function commerceMapping(id) {
  const m = (S.commerce_products || []).find((m) => m.id === id) || {};
  formModal(
    'Map WhatsApp trading item',
    `${field('Meta catalogue ID', 'catalog_id', m.catalog_id || S.settings.whatsapp_catalogue_id)}${field('Meta product retailer ID (same as feed id)', 'retailer_id', m.retailer_id, 'text', 'required')}<label>Trading product<select name="product_id">${selectOptions(
      S.products.filter((p) => p.kind === 'stock'),
      m.product_id,
    )}</select></label>${field('Base units per catalogue item (1 for a bottle)', 'units', m.units || 1, 'number', 'min="1" max="1000" step="1" required')}${dropdown('Price tier', 'price_tier', ['retail', 'wholesale'], m.price_tier || 'retail')}<label class="check"><input type="checkbox" name="active" ${m.active !== 0 ? 'checked' : ''}> Active for orders and export</label>`,
    (data) => mutate('commerce_product', data, 'Trading SKU mapping saved.'),
  );
}
function tradeOrder(id) {
  const o = S.trade_orders.find((o) => o.id === id),
    issues = JSON.parse(o.issues);
  formModal(
    'WhatsApp order ' + esc(id),
    `<p>${esc(o.name)} · +${esc(o.phone)} · Warehouse</p>${table(
      ['Item', 'Base units', 'Current amount'],
      JSON.parse(o.items).map(
        (l) =>
          `<tr><td>${esc(l.name)}<small>Meta SKU ${esc(l.retailer_id)} · ${l.catalogue_quantity} catalogue item(s)</small></td><td>${qty(l.quantity)}</td><td>${rupee(l.price * l.quantity)}</td></tr>`,
      ),
    )}<p>Estimated total: <strong>${rupee(o.total)}</strong></p>${issues.length ? '<div class="notice">' + issues.map(esc).join('<br>') + '</div>' : ''}<p>${o.invoice_id ? 'Invoice ' + esc(o.invoice_id) : 'Not invoiced; stock is not reserved.'}</p>${dropdown('Next status', 'status', ['new', 'confirmed', 'packing', 'ready', 'completed', 'cancelled'], o.status)}<label class="check"><input type="checkbox" name="customer_confirmed_price"> Customer explicitly agreed to any revised prices</label><button type="button" class="btn secondary" onclick="repriceTradeOrder('${esc(id)}')">Recheck mapping, price & stock</button> <button type="button" class="btn secondary" onclick="billTradeOrder('${esc(id)}')">Prepare POS invoice</button>`,
    (data) =>
      mutate(
        'trade_order_status',
        { id, status: data.status, customer_confirmed_price: data.customer_confirmed_price === 'on' },
        'Order status saved; customer/staff updates queued on the active sender.',
      ),
  );
}
async function repriceTradeOrder(id) {
  try {
    await mutate('trade_order_reprice', { id });
    closeModal();
    tradeOrder(id);
  } catch (e) {
    toast(e.message, true);
  }
}
async function billTradeOrder(id) {
  const o = S.trade_orders.find((o) => o.id === id);
  if (o.invoice_id || !['confirmed', 'packing', 'ready'].includes(o.status) || JSON.parse(o.issues).length)
    return toast('Confirm and resolve this unbilled order first.', true);
  if (localLocation() !== 'Warehouse') {
    if (S.online) {
      if (S.web_user.role !== 'owner') return toast('A staff account with Warehouse permissions is required.', true);
      await api('location', { location: 'Warehouse' });
    } else await api('settings', { device_location: 'Warehouse' });
    await load();
  }
  const items = JSON.parse(o.items);
  cart = [];
  for (const l of items) {
    const old = cart.find((r) => r.id === l.product_id);
    if (old) old.quantity += l.quantity;
    else cart.push({ id: l.product_id, quantity: l.quantity });
  }
  window.saleTradeOrder = o.id;
  window.saleDiscount = 0;
  window.priceTier = items[0]?.tier || 'retail';
  window.saleParty =
    S.parties.find((p) => p.kind === 'customer' && String(p.phone).replace(/\D/g, '').endsWith(o.phone.slice(-10)))?.id || '';
  closeModal();
  navTo('billing');
  toast('Order loaded. Confirm payment and save its linked invoice.');
}
