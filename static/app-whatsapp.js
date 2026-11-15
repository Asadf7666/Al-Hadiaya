/* Customer lookup at the counter, WhatsApp updates, campaigns and server pairing. */
function selectBillCustomer(id, close = true) {
  const p = id ? party(id) : null;
  if (p && p.kind !== 'customer') return;
  window.saleParty = p?.id || '';
  window.priceTier = p?.price_tier || 'retail';
  $('#sale-party').value = window.saleParty;
  if ($('#price-tier')) $('#price-tier').value = window.priceTier;
  $('#customer-mobile').value = p?.phone || '';
  refreshCart();
  refreshProducts();
  if (close) closeModal('#product-search');
}
let customerChoices = [],
  customerChoice = 0;
function drawCustomerChoices() {
  const term = $('#customer-query').value.toLowerCase().trim();
  customerChoices = S.parties
    .filter(
      (p) =>
        p.kind === 'customer' &&
        (`${p.name} ${p.phone} ${p.gstin}`.toLowerCase().includes(term) ||
          p.phone.replace(/\D/g, '').includes(term.replace(/\D/g, '') || 'no-phone-match')),
    )
    .slice(0, 25);
  customerChoice = 0;
  $('#customer-choices').innerHTML =
    customerChoices
      .map(
        (p, i) =>
          `<button type="button" data-choice="${i}" class="${i === 0 ? 'selected' : ''}"><strong>${esc(p.name)}</strong><small>${esc(p.phone) || 'No mobile'} · Due ${rupee(p.balance)}</small></button>`,
      )
      .join('') || '<p>No matching customers. Use a walk-in bill or add a profile.</p>';
  $('#customer-choices')
    .querySelectorAll('button')
    .forEach((button) => (button.onclick = () => selectBillCustomer(customerChoices[Number(button.dataset.choice)].id)));
}
function billCustomerForm() {
  openModal(
    'Customer for this bill',
    '<label for="customer-query">Search name or mobile number</label><input id="customer-query" type="search" autocomplete="off" placeholder="Name or mobile; arrows and Enter choose"><p class="status-note">Customer profiles are optional. Choose carefully when names or mobile numbers are shared.</p><div id="customer-choices" class="command-results"></div>',
    '<button type="button" class="btn secondary" onclick="selectBillCustomer(null)">Walk-in customer</button><button type="button" class="btn gold" onclick="addBillCustomer()">Add customer</button>',
  );
  $('#customer-query').oninput = drawCustomerChoices;
  drawCustomerChoices();
}
function addBillCustomer() {
  const phone = $('#customer-query')?.value.replace(/\D/g, '') || '';
  partyForm('customer', null, true);
  if (phone.length === 10) $('#f-phone').value = phone;
}
function findCustomerMobile() {
  const value = $('#customer-mobile').value.replace(/\D/g, '').slice(-10);
  if (value.length !== 10) return toast('Enter a 10-digit mobile number.', true);
  const found = S.parties.filter((p) => p.kind === 'customer' && p.phone.replace(/\D/g, '').slice(-10) === value);
  if (found.length === 1) {
    selectBillCustomer(found[0].id, false);
    $('#product-search').focus();
    toast('Customer selected: ' + found[0].name);
  } else if (found.length > 1) {
    billCustomerForm();
    $('#customer-query').value = value;
    drawCustomerChoices();
  } else {
    partyForm('customer', null, true);
    $('#f-phone').value = value;
    toast('Create an optional customer profile. Walk-in billing remains available.');
  }
}

function notificationsPage() {
  const s = S.settings,
    campaigns = S.campaigns || [],
    templates = S.whatsapp_templates || [];
  if (S.online && S.web_user?.role !== 'owner')
    return heading('WHATSAPP', 'Owner access required', 'An owner manages recipients, templates and campaigns.');
  return (
    heading(
      'WHATSAPP UPDATES',
      'Keep everyone informed.',
      'Internal alerts, customer receipts and approved outreach.',
      `<button class="btn secondary" onclick="whatsappSettings()">Configure sender</button><button class="btn" onclick="sendNotifications()">Process queue</button>`,
    ) +
    `
 <div class="notice">${s.whatsapp_enabled ? 'Automation enabled on this sender.' : 'Notifications paused.'} ${S.whatsapp_token_configured ? 'Sender credential saved.' : 'Configure a sender credential.'}<br>Internal recipients: ${S.internal_contacts.filter((r) => r.opt_in).length} · Branded internal template: ${esc(templates.find((t) => t.name === s.whatsapp_internal_template)?.status || 'Not refreshed')}<br>${S.whatsapp_webhook_configured ? 'Webhook credentials saved; subscribe the public endpoint in Meta to receive delivery updates.' : 'Configure the hosted webhook for delivery status and STOP replies.'} Configure one active sender per business to avoid duplicate messages.</div>
 <div class="card" style="margin-top:20px"><div class="card-head"><div><h2>Customer outreach</h2><p>Separate promotional consent · owner approves every campaign</p></div><button class="text-btn" onclick="campaignForm()">＋ Create campaign</button></div>${table(
   ['Campaign', 'Audience', 'Schedule / status', ''],
   campaigns.map(
     (c) =>
       `<tr><td><strong>${esc(c.name)}</strong><small>${esc(c.template)} · ${esc(c.language)}</small></td><td>${JSON.parse(c.recipients).length} customer(s)</td><td>${esc(c.status)}<small>${c.scheduled ? esc(new Date(c.scheduled).toLocaleString('en-IN')) : 'After approval'}</small></td><td><button class="text-btn" onclick="campaignPreview('${esc(c.id)}')">Review</button> ${c.status !== 'cancelled' ? `<button class="text-btn" onclick="cancelCampaign('${esc(c.id)}')">Cancel</button>` : ''}</td></tr>`,
   ),
 )}</div>${catalogueManagement()}
 <div class="card" style="margin-top:20px"><div class="card-head"><div><h2>Meta templates</h2><p>Prepare text or image campaigns. Meta approval is required before sending.</p></div><button class="text-btn" onclick="refreshTemplates()">Refresh from Meta</button></div>${table(
   ['Name / language', 'Category', 'Meta status', 'Format'],
   templates.map(
     (t) =>
       `<tr><td>${esc(t.name)}<small>${esc(t.language)}</small></td><td>${esc(t.category)}</td><td>${esc(t.status)}</td><td>${t.supported ? (t.header_format === 'IMAGE' ? 'Image + ' : '') + (t.parameter_count || 0) + ' text parameters' : 'Unsupported format'}</td></tr>`,
   ),
 )}<div class="help">Create and submit templates in WhatsApp Manager. Meta must approve them before real customer messages can be sent. <button class="text-btn" onclick="webhookSettings()">Configure delivery webhook</button></div></div>
 <div class="card" style="margin-top:20px"><div class="card-head"><div><h2>Internal recipients</h2><p>Owner, warehouse and café staff · individually opted-in numbers</p></div><button class="text-btn" onclick="internalContact()">＋ Add recipient</button></div>${table(
   ['Name', 'Mobile', 'Notifications', ''],
   S.internal_contacts.map(
     (r) =>
       `<tr><td>${esc(r.name)}</td><td>+${esc(r.phone)}</td><td>${r.opt_in ? 'Enabled' : 'Opted out'}</td><td><button class="text-btn" onclick="internalContact(${r.id})">Edit</button></td></tr>`,
   ),
 )}</div>
 <div class="card" style="margin-top:20px"><div class="card-head"><h2>Recent notification queue</h2><button class="text-btn" onclick="load()">Refresh</button></div>${table(
   ['Created', 'Type / mobile', 'Status', 'Details'],
   S.notifications.map(
     (n) =>
       `<tr><td>${date(n.created)}</td><td>${esc(n.kind)}<small>+${esc(n.phone)}</small></td><td><span class="pill ${['failed', 'uncertain'].includes(n.status) ? 'warn' : ''}">${esc(n.status)}</span><small>${n.attempts} attempt(s)</small></td><td style="white-space:normal">${esc(n.detail || 'Waiting for sender connectivity or scheduled time')}</td></tr>`,
   ),
 )}</div>`
  );
}
function campaignForm() {
  const templates = (S.whatsapp_templates || []).filter((t) => t.category === 'MARKETING' && t.supported);
  if (!templates.length) return toast('Refresh Meta templates before preparing a campaign.', true);
  formModal(
    'Draft customer campaign',
    `${field('Campaign name', 'name', '', 'text', 'required maxlength="100"')}<label>Marketing template<select name="template_key">${templates.map((t, i) => `<option value="${i}">${esc(t.name)} (${esc(t.language)}) · ${esc(t.status)} · ${t.header_format === 'IMAGE' ? 'Image' : 'Text'}</option>`).join('')}</select></label>${imagePicker('Campaign image', 'asset_id', '')}${field('Offer text', 'offer', '', 'text', 'required maxlength="800"')}${dropdown('Customer audience', 'audience', ['All opted-in customers', 'Retail customers', 'Wholesale customers'], 'All opted-in customers')}${field('Schedule (optional, your browser local time)', 'scheduled', '', 'datetime-local')}<div class="help">Only customers with separate promotional consent are included. Duplicate mobile numbers receive one message. Saving creates a draft; no messages are sent until you review and approve it. Image templates require an image. Templates without placeholders use fixed Meta text; the offer field then remains an internal note.</div>`,
    async (data) => {
      const t = templates[Number(data.template_key)];
      const ids = S.parties
        .filter(
          (p) =>
            p.kind === 'customer' &&
            p.whatsapp_marketing_opt_in &&
            (!data.audience ||
              data.audience === 'All opted-in customers' ||
              p.price_tier === (data.audience === 'Retail customers' ? 'retail' : 'wholesale')),
        )
        .map((p) => p.id);
      const r = await mutate(
        'campaign_create',
        {
          name: data.name,
          offer: data.offer,
          template: t.name,
          language: t.language,
          customer_ids: ids,
          asset_id: data.asset_id,
          scheduled: data.scheduled ? new Date(data.scheduled).toISOString() : '',
        },
        'Campaign saved as draft.',
      );
      setTimeout(() => campaignPreview(r.id), 50);
    },
  );
}
function campaignPreview(id) {
  const c = (S.campaigns || []).find((c) => c.id === id);
  if (!c) return;
  const audience = JSON.parse(c.recipients),
    t = (S.whatsapp_templates || []).find((t) => t.name === c.template && t.language === c.language);
  const preview = (t?.body || '{{1}} · {{2}} · {{3}}')
    .replaceAll('{{1}}', audience[0]?.name || 'Customer')
    .replaceAll('{{2}}', S.settings.name)
    .replaceAll('{{3}}', c.offer);
  openModal(
    'Review campaign',
    `<p><strong>${esc(c.name)}</strong> · ${audience.length} customers</p>${c.asset_id ? `<img src="/media/${esc(c.asset_id)}" alt="Campaign image" style="width:100%;max-height:340px;object-fit:contain;border-radius:12px">` : ''}<div class="notice" style="white-space:pre-wrap">${esc(preview)}</div><p>${c.scheduled ? 'Scheduled: ' + esc(new Date(c.scheduled).toLocaleString('en-IN')) : 'Queue after owner approval; sends when automation is enabled and online.'}</p><p>${audience
      .slice(0, 10)
      .map((r) => `${esc(r.name)} (+${esc(r.phone)})`)
      .join(
        '<br>',
      )}${audience.length > 10 ? '<br>…' : ''}</p><div class="help">Consent is checked again before each send. Reply STOP opts out when the hosted webhook is subscribed. Meta messaging charges may apply.</div>${c.status === 'draft' ? `<button class="btn" onclick="approveCampaign('${esc(c.id)}')">Approve ${audience.length} recipients</button>` : `<span class="pill">${esc(c.status)}</span>`}`,
  );
}
async function approveCampaign(id) {
  try {
    const r = await mutate('campaign_approve', { id, confirmed: true });
    closeModal();
    toast(r.queued + ' messages queued.');
  } catch (e) {
    toast(e.message, true);
  }
}
async function cancelCampaign(id) {
  if (!confirm('Cancel messages that have not started sending?')) return;
  try {
    await mutate('campaign_cancel', { id }, 'Pending messages cancelled.');
  } catch (e) {
    toast(e.message, true);
  }
}
async function refreshTemplates() {
  try {
    const r = await mutate('whatsapp_templates', {});
    toast(r.count + ' templates refreshed.');
  } catch (e) {
    toast(e.message, true);
  }
}
function webhookSettings() {
  formModal(
    'Hosted WhatsApp webhook',
    `<div class="notice">Callback URL: ${esc(S.online ? location.origin + '/webhooks/whatsapp' : 'Use your hosted app HTTPS address + /webhooks/whatsapp')}</div>${field('Meta app secret (blank keeps saved)', 'app_secret', '', 'password', 'autocomplete="new-password"')}${field('Verification token you choose (16+ characters)', 'verify_token', '', 'password', 'autocomplete="new-password"')}<div class="help">Find the app secret in Meta app settings. After saving, enter this callback URL and the same verification token in Meta, then subscribe the messages field. These credentials stay on this sender and are excluded from sync.</div>`,
    (data) => mutate('whatsapp_webhook', data, 'Webhook credentials saved. Configure the subscription in Meta.'),
  );
}
function internalContact(id) {
  const r = S.internal_contacts.find((r) => r.id === id) || {};
  formModal(
    'Internal WhatsApp recipient',
    `${field('Staff / owner name', 'name', r.name, 'text', 'required')}${field('Mobile number', 'phone', r.phone, 'tel', 'required')}<label class="check"><input type="checkbox" name="opt_in" ${r.opt_in ? 'checked' : ''}> This recipient agreed to internal WhatsApp updates</label>`,
    (data) => mutate('internal_contact', { ...data, id }, 'Recipient saved.'),
  );
}
function whatsappSettings() {
  const s = S.settings;
  formModal(
    'WhatsApp Business automation',
    `${s.whatsapp_pause_reason ? '<div class="notice">' + esc(s.whatsapp_pause_reason) + '</div>' : ''}<label class="check"><input type="checkbox" name="whatsapp_enabled" ${s.whatsapp_enabled ? 'checked' : ''}> Enable notifications on this sender</label><div class="form-grid">${field('Meta sender phone-number ID', 'whatsapp_phone_id', s.whatsapp_phone_id)}${field('WhatsApp Business Account ID', 'whatsapp_waba_id', s.whatsapp_waba_id)}${dropdown('Notification timezone', 'whatsapp_timezone', ['Asia/Kolkata', 'UTC'], s.whatsapp_timezone || 'Asia/Kolkata')}${field('Supported Graph API version', 'whatsapp_api_version', s.whatsapp_api_version, 'text', 'placeholder="Use version from your Meta console"')}${field('Template language code', 'whatsapp_language', s.whatsapp_language)}${field('Access token (blank keeps existing)', 'token', '', 'password', 'autocomplete="new-password"')}${field('Approved invoice template', 'whatsapp_invoice_template', s.whatsapp_invoice_template)}${field('Approved payment template', 'whatsapp_payment_template', s.whatsapp_payment_template)}${field('Approved internal update template', 'whatsapp_internal_template', s.whatsapp_internal_template)}${field('Daily summary time (selected notification timezone)', 'whatsapp_daily_time', s.whatsapp_daily_time, 'time')}</div>${['low_stock', 'transfers', 'purchases', 'sales', 'payments', 'expenses', 'reversals', 'profiles', 'catalogue', 'stock', 'recipes', 'orders'].map((k) => `<label class="check"><input type="checkbox" name="whatsapp_${k}" ${s['whatsapp_' + k] ? 'checked' : ''}> ${k.replaceAll('_', ' ')}</label>`).join('')}<div class="help">Keep sending disabled while a Meta restriction or review is pending. Use approved body-only templates with exactly three text parameters: invoice = customer, invoice number, amount; payment = customer, amount, note; internal = business, update type, summary. Configure matching language codes in Meta. Recipients must opt in. Meta account setup and messaging charges apply. The token stays on this PC; Windows protects it for your Windows account.</div>`,
    (data) => {
      for (const key of [
        'whatsapp_enabled',
        'whatsapp_low_stock',
        'whatsapp_transfers',
        'whatsapp_purchases',
        'whatsapp_sales',
        'whatsapp_payments',
        'whatsapp_expenses',
        'whatsapp_reversals',
        'whatsapp_profiles',
        'whatsapp_catalogue',
        'whatsapp_stock',
        'whatsapp_recipes',
        'whatsapp_orders',
      ])
        data[key] = data[key] === 'on';
      return mutate('whatsapp_settings', data, 'WhatsApp configuration saved.');
    },
  );
}
async function sendNotifications() {
  try {
    const r = await api('whatsapp_send');
    await load();
    toast(r.message || 'Processed ' + r.processed + ' queued notification(s).');
  } catch (e) {
    toast(e.message, true);
  }
}

function cloudPairForm() {
  formModal(
    'Connect this PC to your online business',
    `${field('Server HTTPS address', 'url', '', 'url', 'required placeholder="https://your-business-server"')}${field('One-time pairing code', 'code', '', 'password', 'required autocomplete="off"')}${field('Name for this PC', 'peer_name', S.settings.device_name || 'Warehouse Till', 'text', 'required')}<label class="check"><input type="checkbox" name="replace_sample" required> This PC contains only sample/test records. Replace them with the server records after a backup.</label><div class="help">Existing local records are backed up first. This flow does not merge real trading records. Pairing codes expire after 10 minutes. Location is a default, not a permissions restriction. Every paired node can perform all business operations. Use a permanent server for live business.</div>`,
    async (data) => {
      data.replace_sample = data.replace_sample === 'on';
      data.name = data.peer_name;
      delete data.peer_name;
      const r = await api('cloud_pair', data);
      cart = [];
      window.saleParty = '';
      await load();
      toast(r.message);
    },
    'Back up & connect',
  );
}

function serverAddressForm() {
  formModal(
    'Update server address',
    `${field('Server HTTPS address', 'url', S.settings.cloud_url, 'url', 'required')}<div class="help">Use this when the same server’s IP or domain changes. Your existing records, pending transactions and credential are preserved. The app verifies that the address belongs to the same business before changing it.</div>`,
    (data) => mutate('cloud_address', data, 'Server address updated. Click Sync now.'),
  );
}
