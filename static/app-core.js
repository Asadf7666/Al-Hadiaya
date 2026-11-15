/* Shared state, helpers, server calls, navigation and page rendering. */
let historySince = ''; // Earliest date of history to load; empty means the recent window.
let draftLoaded = false;
let S,
  token,
  page = 'overview',
  cart = [],
  purchaseCart = [],
  category = 'All',
  query = '',
  stockFilter = 'All',
  peopleFilter = 'customer';
const $ = (s) => document.querySelector(s),
  esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const rupee = (n) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format((n || 0) / 100);
const qty = (n) => Number(Number(n || 0).toFixed(3)).toLocaleString('en-IN');
const businessDay = (value) =>
    new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).format(
      new Date(value),
    ),
  today = () => businessDay(new Date()),
  date = (s) => new Date(s).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
const sum = (a, key) => a.reduce((n, r) => n + (typeof key === 'function' ? key(r) : Number(r[key] || 0)), 0);
let indexState = null,
  productIndex = new Map(),
  partyIndex = new Map(),
  stockIndex = new Map(),
  scanIndex = new Map(),
  searchIndex = new Map(),
  posOffset = 0,
  inventoryOffset = 0,
  peopleOffset = 0,
  peopleQuery = '',
  activeCartId = null,
  productSearchTimer = null,
  productViewState = null,
  productViewQuery = '',
  productViewCategory = '',
  productViewTier = '',
  productViewOffset = 0,
  productViewHost = null;
const PAGE_SIZE = 60,
  RECORD_PAGE_SIZE = 100;
function ensureIndexes() {
  if (indexState === S) return;
  indexState = S;
  productIndex = new Map();
  partyIndex = new Map();
  stockIndex = new Map();
  scanIndex = new Map();
  searchIndex = new Map();
  for (const p of S.products) {
    productIndex.set(p.id, p);
    searchIndex.set(p.id, `${p.name} ${p.sku} ${p.barcode || ''} ${p.brand || ''} ${p.size || ''}`.toLowerCase());
    for (const code of new Set([p.sku, p.barcode].filter(Boolean))) {
      if (scanIndex.has(code) && scanIndex.get(code)?.id !== p.id) scanIndex.set(code, null);
      else if (!scanIndex.has(code)) scanIndex.set(code, p);
    }
  }
  for (const p of S.parties) partyIndex.set(p.id, p);
  for (const r of S.stocks) stockIndex.set(r.product_id + ':' + r.location, r.quantity);
}
const product = (id) => {
    ensureIndexes();
    return productIndex.get(Number(id));
  },
  party = (id) => {
    ensureIndexes();
    return partyIndex.get(Number(id));
  },
  stock = (id, loc) => {
    ensureIndexes();
    return stockIndex.get(id + ':' + loc) || 0;
  };
function scanProduct(value) {
  ensureIndexes();
  return scanIndex.get(value.trim());
}
function matchingProducts(text = query) {
  ensureIndexes();
  const term = text.trim().toLowerCase();
  return S.products.filter((p) => searchIndex.get(p.id).includes(term));
}
function pageControls(start, total, size, handler) {
  return `<div class="record-pager" role="group" aria-label="Results pages"><span role="status">${total ? start + 1 : 0}–${Math.min(start + size, total)} of ${total}</span><button type="button" class="btn secondary small" onclick="${handler}(-1)" ${start <= 0 ? 'disabled' : ''}>Previous · Page Up</button><button type="button" class="btn secondary small" onclick="${handler}(1)" ${start + size >= total ? 'disabled' : ''}>Next · Page Down</button></div>`;
}
const liveDocs = () => S.documents.filter((d) => !d.reversed),
  localLocation = () => S.settings.device_location || 'Outlet';
const iconPaths = {
  overview: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  billing: 'M4 3h16v18l-4-2-4 2-4-2-4 2z M8 7h8 M8 11h8 M8 15h4',
  inventory: 'M3 6l9-4 9 4-9 5z M3 6v12l9 4 9-4V6 M12 11v11',
  purchases: 'M3 5h2l3 12h10l3-9H6 M9 21h.01 M18 21h.01',
  cafe: 'M4 4h13v8a6.5 6.5 0 0 1-13 0z M17 5h2a3 3 0 0 1 0 6h-2 M2 21h19',
  people: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M13 3a4 4 0 1 1 0 8 M20 21v-2a4 4 0 0 0-3-3 M9 3a4 4 0 1 0 0 8a4 4 0 0 0 0-8',
  reports: 'M4 21h17 M7 17V9 M12 17V3 M17 17v-5',
  settings: 'M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',
};
iconPaths.notifications = iconPaths.people;
iconPaths.orders = iconPaths.inventory;
const pages = {
  overview: 'Overview',
  billing: 'Billing & invoices',
  inventory: 'Inventory & transfers',
  purchases: 'Purchases',
  cafe: 'Café menu',
  people: 'Customers & suppliers',
  reports: 'Reports & expenses',
  orders: 'WhatsApp orders',
  notifications: 'WhatsApp updates',
  settings: 'Settings & sync',
};
const icon = (k) => `<svg viewBox="0 0 24 24"><path d="${iconPaths[k]}" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
function toast(text, error = false) {
  $('#toast').textContent = text;
  $('#toast').className = error ? 'error-toast' : '';
  $('#toast').style.display = 'block';
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(() => ($('#toast').style.display = 'none'), 6500);
}
const pendingRequests = new Map();
async function api(action, data = {}) {
  const key = JSON.stringify([action, data]),
    financial = [
      'sale',
      'purchase',
      'payment',
      'expense',
      'transfer',
      'adjust',
      'reverse',
      'return',
      'stock_count',
      'purchase_order_create',
      'purchase_order_status',
    ].includes(action);
  let storageKey = '',
    saved = '';
  if (financial && S) {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(key));
    storageKey =
      'alhadiya-retry:' + billDraftKey() + ':' + Array.from(new Uint8Array(digest), (n) => n.toString(16).padStart(2, '0')).join('');
    try {
      saved = sessionStorage.getItem(storageKey) || '';
    } catch {}
  }
  const requestId =
    pendingRequests.get(key) ||
    saved ||
    Array.from(crypto.getRandomValues(new Uint8Array(16)), (n) => n.toString(16).padStart(2, '0')).join('');
  pendingRequests.set(key, requestId);
  if (storageKey)
    try {
      sessionStorage.setItem(storageKey, requestId);
    } catch {}
  let r,
    parsed = false;
  try {
    r = await fetch('/api/' + action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Shop-Token': token, 'X-Request-ID': requestId },
      body: JSON.stringify(data),
    });
    const body = await r.json();
    parsed = true;
    if (r.status === 401) {
      location.href = '/login';
      throw Error('Please sign in again.');
    }
    if (!r.ok) {
      if (r.status < 500) {
        pendingRequests.delete(key);
        if (storageKey) sessionStorage.removeItem(storageKey);
      }
      throw Error(body.error || 'Unable to save. Review the form.');
    }
    pendingRequests.delete(key);
    if (storageKey) sessionStorage.removeItem(storageKey);
    return body;
  } catch (e) {
    if (!r || !parsed) throw Error('Response interrupted. Review saved records, then retry this same operation to avoid duplicates.');
    throw e;
  }
}

async function load() {
  const r = await fetch('/api/state' + (historySince ? '?since=' + historySince : ''));
  if (r.status === 401) {
    location.href = '/login';
    throw Error('Please sign in again.');
  }
  if (!r.ok) throw Error('App connection interrupted. Saved records remain safe.');
  S = await r.json();
  if (!draftLoaded) {
    restoreBillDraft();
    draftLoaded = true;
  }
  $('#device-badge').textContent = S.settings.device_location || 'Warehouse + Outlet';
  $('#sync-status').textContent = S.settings.last_sync
    ? 'Last exchange: ' + new Date(S.settings.last_sync).toLocaleTimeString()
    : S.settings.cloud_url
      ? 'Server paired · awaiting first exchange'
      : 'Sync folder not connected';
  if (!S.online && (!S.web_user || S.web_user.role === 'owner') && S.settings.node_mode === 'unified' && !$('#node-location')) {
    const select = document.createElement('select');
    select.id = 'node-location';
    select.style.cssText = 'width:125px;padding:6px';
    select.innerHTML = ['Warehouse', 'Outlet'].map((l) => `<option>${l}</option>`).join('');
    select.onchange = async () => {
      try {
        await api(S.web_user ? 'location' : 'settings', S.web_user ? { location: select.value } : { device_location: select.value });
        cart = [];
        await load();
      } catch (e) {
        toast(e.message, true);
      }
    };
    $('.header-right').prepend(select);
  }
  if ($('#node-location')) $('#node-location').value = S.settings.device_location || 'Warehouse';
  render();
}
async function mutate(action, data, message) {
  const r = await api(action, data);
  await load();
  if (message) toast(message);
  return r;
}
function navTo(name) {
  posOffset = 0;
  inventoryOffset = 0;
  peopleOffset = 0;
  if (!pageAllowed(name)) return toast('Your role does not allow this screen.', true);
  page = name;
  query = '';
  category = 'All';
  render();
  window.scrollTo(0, 0);
}
function pageAllowed(name) {
  const r = S?.web_user?.role || 'owner';
  return r === 'owner' || r === 'manager'
    ? !(['settings', 'notifications'].includes(name) && r !== 'owner')
    : r === 'cashier'
      ? ['overview', 'billing', 'people', 'staff'].includes(name)
      : ['overview', 'people', 'staff'].includes(name);
}
function canOperate(action) {
  const r = S?.web_user?.role || 'owner';
  return (
    r === 'owner' ||
    (r === 'manager' && action !== 'backup') ||
    (r === 'cashier' && ['sale', 'party', 'expense', 'shift_open', 'shift_close'].includes(action))
  );
}
function render() {
  if (!S) return;
  $('#nav').innerHTML = Object.entries(pages)
    .filter(([k]) => pageAllowed(k))
    .map(([k, v]) => `<button class="${page === k ? 'active' : ''}" onclick="navTo('${k}')">${icon(k)}<span>${v}</span></button>`)
    .join('');
  $('#page-label').textContent = pages[page];
  $('#main').innerHTML = {
    planning: planningPage,
    orders: ordersPage,
    notifications: notificationsPage,
    overview: overview,
    billing: billing,
    inventory: inventory,
    purchases: purchases,
    cafe: cafe,
    people: people,
    reports: reports,
    settings: settings,
  }[page]();
  bindPage();
}
const heading = (tag, title, sub, actions = '') =>
  `<div class="page-heading"><div><div class="eyebrow">${tag}</div><h1>${title}</h1><p>${sub}</p></div><div class="actions">${actions}</div></div>`;
const empty = (text) => `<div class="empty">${text}</div>`;
const table = (heads, rows) =>
  `<div class="table-wrap"><table><thead><tr>${heads.map((h) => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>${!rows.length ? empty('No records yet. Add your first entry to get started.') : ''}</div>`;
const selectOptions = (rows, selected) =>
  rows.map((r) => `<option value="${esc(r.id)}" ${String(r.id) === String(selected) ? 'selected' : ''}>${esc(r.name)}</option>`).join('');
const symbol = (c) =>
  ({
    'Cold drinks': '🥤',
    Water: '◈',
    'Packaged water': '◈',
    Juices: '🍊',
    'Energy drinks': 'ϟ',
    'Ice cream': '🍦',
    Snacks: '▧',
    Coffee: '☕',
    'Tea & coffee': '☕',
    Mojitos: '🍃',
    Ingredients: '◌',
    'Dairy & milk': '🥛',
  })[c] || '▣';
