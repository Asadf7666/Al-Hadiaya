/* Shared keyboard access for the desktop and hosted workspace. */
(() => {
  const $ = selector => document.querySelector(selector);
  const routes = [
    ['1', 'overview'], ['2', 'billing'], ['3', 'inventory'], ['4', 'purchases'],
    ['5', 'cafe'], ['6', 'people'], ['7', 'reports'], ['8', 'planning'],
    ['9', 'orders'], ['0', 'notifications'], ['s', 'settings'], ['t', 'staff']
  ];
  let navigating = false, opener = null, palette = [], selected = 0, scheduled = false, dialogVersion = 0;
  const available = el => !!el && !el.disabled && !el.closest('[inert]') && el.getClientRects().length > 0;
  function remember(el = document.activeElement) {
    if (!el || el === document.body) return null;
    const result = {el, id:el.id, key:el.dataset.kbKey, click:el.getAttribute('onclick'), text:el.textContent?.trim(), tag:el.tagName};
    if (el.matches('input:not([type=password]),textarea')) {
      result.value = el.value;
      try {result.start = el.selectionStart; result.end = el.selectionEnd;} catch {}
    }
    return result;
  }
  function restore(saved, preserveValue = false) {
    if (!saved) return false;
    let el = available(saved.el) ? saved.el : saved.id ? document.getElementById(saved.id) : null;
    if (!available(el) && saved.key) el = document.querySelector('[data-kb-key="'+CSS.escape(saved.key)+'"]');
    if (!available(el) && saved.click) el = [...document.querySelectorAll('[onclick]')].find(e => available(e) && e.getAttribute('onclick') === saved.click);
    if (!available(el) && saved.text) el = [...document.querySelectorAll('button,a[href]')].find(e => available(e) && e.tagName === saved.tag && e.textContent.trim() === saved.text);
    if (!available(el)) return false;
    if (preserveValue && saved.value !== undefined && el.matches('input:not([type=password]),textarea')) el.value = saved.value;
    el.focus({preventScroll:true});
    if (saved.start != null) try {el.setSelectionRange(saved.start, saved.end);} catch {}
    return true;
  }
  function sidebar() {
    const aside = $('.sidebar'), button = $('#mobile-menu');
    if (!aside) return;
    const open = innerWidth > 850 || aside.classList.contains('open');
    aside.inert = !open;
    aside.setAttribute('aria-hidden', String(!open));
    if (button) {button.setAttribute('aria-expanded', String(open)); button.setAttribute('aria-controls', 'sidebar-navigation');}
    if ($('#nav-backdrop')) $('#nav-backdrop').tabIndex = -1;
  }
  function enhance() {
    sidebar();
    const main = $('#main');
    if (main) main.tabIndex = -1;
    document.querySelectorAll('#nav button').forEach(button => {
      const route = button.getAttribute('onclick')?.match(/navTo\('([^']+)/)?.[1];
      if (!route) return;
      button.dataset.kbKey = 'nav-'+route;
      button.classList.toggle('active',page===route);
      button.setAttribute('aria-label', pages[route] || button.textContent.trim());
      if (page === route) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
      const shortcut = routes.find(([,name]) => name === route);
      if (shortcut) {button.setAttribute('aria-keyshortcuts', 'Alt+'+shortcut[0]); button.title = (pages[route] || route)+' · Alt+'+shortcut[0].toUpperCase();}
    });
    document.querySelectorAll('.tabs').forEach((tabs, group) => {
      tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', group === 0 ? 'View filters' : 'Additional filters');
      tabs.querySelectorAll('button').forEach((button, index) => {
        button.setAttribute('role','tab'); button.setAttribute('aria-selected',String(button.classList.contains('active')));
        button.tabIndex = button.classList.contains('active') ? 0 : -1;
        button.dataset.kbKey = 'filter-'+group+'-'+(button.dataset.category || button.textContent.trim());
      });
    });
    document.querySelectorAll('.product-card').forEach(button => {
      button.dataset.kbKey = 'product-'+(button.getAttribute('onclick')?.match(/addCart\((\d+)/)?.[1] || button.textContent.trim());
      button.setAttribute('aria-label',button.textContent.trim().replace(/\s+/g,' '));
    });
    document.querySelectorAll('.cart-line').forEach(line => {
      const name = line.querySelector('strong')?.textContent || 'item';
      line.querySelectorAll('button').forEach(button => {
        if (['+','＋'].includes(button.textContent.trim())) button.setAttribute('aria-label','Increase '+name+' quantity');
        if (['−','-'].includes(button.textContent.trim())) button.setAttribute('aria-label','Decrease '+name+' quantity');
      });
      line.querySelector('input[type=number]')?.setAttribute('aria-label', name+' quantity');
    });
    for (const [selector, names] of [['.purchase-line',['Product','Quantity','Cost per unit']],['.recipe-line',['Ingredient','Quantity per serving']]]) {
      document.querySelectorAll(selector).forEach((row, index) => row.querySelectorAll('select,input').forEach((el,n) => {
        const label=selector==='.purchase-line'?(el.matches('[data-purchase-search]')?'Product':el.matches('[data-qty]')?'Quantity':el.matches('[data-price]')?'Cost per unit':'Selected product'):(names[n]||'Value');el.setAttribute('aria-label',label+' '+(index+1));
      }));
    }
    for (const [id, label] of [['node-location','Transaction location'],['online-location','Transaction location'],['sale-party','Customer for current bill'],['discount','Bill discount in rupees']]) document.getElementById(id)?.setAttribute('aria-label',label);
    document.querySelector('.cart-head select:not([id])')?.setAttribute('aria-label','Selling price tier');
    document.querySelectorAll('input,select,textarea').forEach(el => {
      if (el.type === 'hidden' || el.hasAttribute('aria-label') || el.labels?.length) return;
      const label = el.closest('.field')?.querySelector('label')?.textContent || el.placeholder || el.name;
      if (label) el.setAttribute('aria-label',label);
    });
    document.querySelectorAll('.table-wrap').forEach(el => {
      el.tabIndex = 0; el.setAttribute('role','region');
      el.setAttribute('aria-label',(el.closest('.card')?.querySelector('h2')?.textContent || 'Records')+' table; use arrow keys to scroll');
    });
    if ($('#product-search')) {
      $('#product-search').setAttribute('aria-label','Search products or scan barcode');
      $('#product-search').setAttribute('aria-keyshortcuts','F3');
      $('#product-search').title = 'F3 to search; Down chooses a result; Enter adds; Page Up/Down browses more products';
    }
    const dialog = $('#modal');
    if (dialog) {
      const title = dialog.querySelector('h2');
      if (title) {title.id = 'dialog-title'; title.tabIndex = -1; dialog.setAttribute('aria-labelledby',title.id);}
      dialog.setAttribute('aria-modal','true');
      dialog.querySelectorAll('.error').forEach(el => el.setAttribute('role','alert'));
    }
    if ($('.header-right') && !$('#keyboard-help')) {
      const button = document.createElement('button'); button.id = 'keyboard-help'; button.className = 'btn secondary small';
      button.textContent = '⌨'; button.setAttribute('aria-label','Keyboard shortcuts'); button.title = 'Keyboard shortcuts · Alt+K';
      button.onclick = help; $('.header-right').appendChild(button);
    }
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true; requestAnimationFrame(() => {scheduled = false; enhance();});
  }
  function focusMain() {$('#main')?.focus({preventScroll:true});}
  function go(route) {if (pageAllowed(route)) navTo(route); else toast('Your role does not allow this page.',true);}
  function help() {
    if ($('#modal').open) return;
    const shortcuts = [['Ctrl+K / ⌘K','Find a page or action'],['Alt+1 … Alt+0','Open business pages'],['Alt+S / Alt+T','Settings / staff'],['F2','Open POS; keep current basket'],['F3','Search this page / scan a purchase item'],['F4','Add or receive on this page'],['F5 / F6 / F7','Bill customer / quantity / discount'],['F8','Open checkout'],['F10','Print the open invoice'],['Enter / Shift+Enter','Next / previous form field'],['Page Up / Page Down','Previous / next results page'],['Alt+C/U/D/B','Checkout: Cash / UPI / Card / Bank'],['Alt+A / Alt+P','Purchase: add item / amount paid'],['F9','Invoice history'],['Ctrl+Enter / ⌘Enter','Submit the current form'],['Esc','Close a dialog or navigation'],['Tab / Shift+Tab','Next / previous control'],['Arrow keys','Choose product cards or view tabs'],['Alt+N / Alt+M','Focus navigation / workspace'],['Alt+L','Focus location selector'],['Alt+K','This shortcut guide']];
    openModal('Keyboard shortcuts','<p>Keyboard access works offline. Saving still uses the normal validation and confirmation screens.</p>'+table(['Shortcut','Action'],shortcuts.map(([key,value])=>'<tr><td><kbd>'+esc(key)+'</kbd></td><td>'+esc(value)+'</td></tr>')),'<button class="btn secondary" onclick="closeModal()">Close</button>');
  }
  function actions() {
    const aliases={billing:'pos bill invoice sale barcode checkout',inventory:'stock products sku catalogue warehouse transfers',cafe:'coffee mojito cafe menu ingredients',people:'profiles customer supplier mobile credit ledger',planning:'reorder procurement purchasing stock alerts',reports:'sales expenses payments report',staff:'users permissions accounts',settings:'sync gst tax backup printer'};const result=Object.keys(pages).filter(pageAllowed).map(route=>({title:pages[route],keywords:aliases[route]||'',group:'Page',run:()=>go(route)}));
    function add(title,group,permission,run) {if (canOperate(permission)) result.push({title,group,run});}
    add('Add product','Inventory','product',()=>{go('inventory');productForm();});
    add('Transfer stock','Inventory','transfer',()=>{go('inventory');transferForm();});
    add('Receive supplier purchase','Purchases','purchase',()=>{go('purchases');purchaseForm();});
    add('Add customer','Profiles','party',()=>{go('people');partyForm('customer');});
    if (['owner','manager'].includes(S.web_user?.role)) add('Add supplier','Profiles','party',()=>{go('people');partyForm('supplier');});
    add('Add café menu item','Café','product',()=>{go('cafe');productForm(null,true);});
    if (pageAllowed('cafe')) add('Open café POS','Café','sale',()=>openCafePOS());
    add('Record expense','Reports','expense',()=>expenseForm());
    add('Draft purchase order','Planning','purchase_order_create',()=>{go('planning');purchaseOrderForm();});
    if (pageAllowed('notifications')) result.push({title:'Draft WhatsApp campaign',group:'WhatsApp',run:()=>{go('notifications');campaignForm();}});
    if (S.web_user?.role === 'owner') result.push({title:'Add staff account',group:'Staff',run:()=>{go('staff');staffForm();}});
    add('Back up now','Recovery','backup',()=>runBackup());
    return result;
  }
  function drawPalette() {
    const query = $('#command-query').value.toLowerCase(); palette = actions().filter(a=>(a.title+' '+a.group+' '+(a.keywords||'')).toLowerCase().includes(query));
    selected = 0;
    $('#command-results').innerHTML = palette.length ? palette.map((a,i)=>'<button type="button" data-command="'+i+'"><strong>'+esc(a.title)+'</strong><small>'+esc(a.group)+'</small></button>').join('') : '<p>No matching actions for your account.</p>';
    $('#command-results').querySelectorAll('button').forEach(button => button.onclick = () => choose(Number(button.dataset.command)));
    $('#command-count').textContent = palette.length+' matching action'+(palette.length===1?'':'s'); highlight();
  }
  function highlight() {
    $('#command-results')?.querySelectorAll('button').forEach((button,i)=> {button.classList.toggle('selected',i===selected);button.setAttribute('aria-current',i===selected?'true':'false');});
    $('#command-results button.selected')?.scrollIntoView({block:'nearest'});
  }
  function choose(index) {const action = palette[index]; if (action) {closeModal(); action.run();}}
  function commands() {
    if ($('#modal').open) return;
    openModal('Find a page or action','<label for="command-query">Search the business workspace</label><input id="command-query" placeholder="Try stock, customer, café or purchase…" autocomplete="off" aria-describedby="command-instructions"><p id="command-instructions">Type to filter. Use Up/Down and Enter to choose, or Tab to a result.</p><div id="command-results" class="command-results"></div><p id="command-count" role="status"></p>');
    $('#command-query').oninput = drawPalette; drawPalette();
  }
  function focusSearch() {
    const names={billing:'#product-search',inventory:'#inventory-search',people:'#people-search'};
    const field=$(names[page]||'#missing-search');
    if(field){field.focus();field.select();}else commands();
  }
  function openPOS() {if(!pageAllowed('billing'))return; if(page!=='billing')go('billing');$('#product-search')?.focus();$('#product-search')?.select();}
  function focusQuantity(){const id=activeCartId||cart.at(-1)?.id;const field=$('.cart-line[data-product-id="'+id+'"] [data-cart-quantity]');if(field){field.focus();field.select();}else toast('Add a product first.');}
  function nextField(target,back=false){
    const form=target.closest('form');if(!form)return;
    const fields=[...form.querySelectorAll('input:not([type=hidden]):not([type=file]),select,textarea')].filter(el=>available(el)&&!el.readOnly);
    if(!back&&!target.reportValidity())return;
    const index=fields.indexOf(target),field=fields[index+(back?-1:1)]||(!back?$('#form-submit')||form.querySelector('[type=submit]'):null);
    if(field){field.focus();if(field.matches('input:not([type=checkbox]),textarea'))field.select();}
  }
  function purchaseSearch(dialog){const current=document.activeElement.closest('.purchase-line');const rows=[...dialog.querySelectorAll('.purchase-line')];const row=current||rows.find(r=>!r.querySelector('select').value)||addPurchaseLine();const field=row?.querySelector('[data-purchase-search]');if(field){field.focus();field.select();}}
  function highlightPurchase(row){row.querySelectorAll('[data-choice]').forEach((button,i)=>button.setAttribute('aria-selected',String(i===row.purchaseChoice)));const chosen=row.querySelector('[data-choice="'+row.purchaseChoice+'"]');if(chosen){row.querySelector('[data-purchase-search]').setAttribute('aria-activedescendant',chosen.id);chosen.scrollIntoView({block:'nearest'});}}
  function choosePurchase(row){const input=row.querySelector('[data-purchase-search]');if(!input.value.trim())return toast('Enter a product name or barcode first.');const exact=scanProduct(input.value);if(exact===null){input.setCustomValidity('Code matches more than one product. Correct the catalogue.');input.reportValidity();return;}
    let p=exact;if(!p&&/^\d{6,}$/.test(input.value.trim())){input.setCustomValidity('Barcode not found. Check the catalogue.');input.reportValidity();return;}
    if(!p&&row.querySelector('select').value)p=product(row.querySelector('select').value);
    if(!p){if(!row.purchaseChoices?.length)purchaseChoices(row);p=row.purchaseChoices?.[row.purchaseChoice||0];}
    if(p&&selectPurchaseProduct(row,p.id)){const field=row.querySelector('[data-qty]');field.focus();field.select();}else{input.setCustomValidity('Choose a stocked product or café ingredient.');input.reportValidity();}
  }
  function primaryAction() {
    const map = {inventory:()=>productForm(),purchases:()=>purchaseForm(),cafe:()=>productForm(null,true),people:()=>partyForm(peopleFilter),reports:()=>expenseForm(),planning:()=>purchaseOrderForm(),notifications:()=>campaignForm(),staff:()=>staffForm()};
    const permission = {inventory:'product',purchases:'purchase',cafe:'product',people:'party',reports:'expense',planning:'purchase_order_create',notifications:'whatsapp_settings',staff:'staff_user'}[page];
    if (['staff','notifications'].includes(page) && S.web_user?.role!=='owner') return;
    if (map[page] && canOperate(permission)) map[page]();
  }
  function grid(event, button) {
    const cards = [...button.closest('.product-grid').querySelectorAll('.product-card')].filter(available);
    if (!cards.length) return;
    const index = cards.indexOf(button), columns = cards.filter(el=>Math.abs(el.getBoundingClientRect().top-cards[0].getBoundingClientRect().top)<2).length;
    let next = index;
    if (event.key==='ArrowRight') next++; if (event.key==='ArrowLeft') next--;
    if (event.key==='ArrowDown') next+=columns; if (event.key==='ArrowUp') next-=columns;
    if (event.key==='Home') next=0; if (event.key==='End') next=cards.length-1;
    event.preventDefault();cards[Math.max(0,Math.min(cards.length-1,next))].focus();
  }
  document.addEventListener('keydown',event => {
    if (event.isComposing || event.ctrlKey && event.altKey || typeof S==='undefined' || !S) return;
    const key = event.key, lower = key.toLowerCase(), dialog = $('#modal'), target = event.target;
    if (event.repeat && ['Enter','F8','F10'].includes(key)) {event.preventDefault();event.stopImmediatePropagation();return;}
    if (dialog.open) {
      if (key==='Tab') {
        const fields=[...dialog.querySelectorAll('button,a[href],input:not([type=hidden]),select,textarea,[tabindex]')].filter(el=>available(el)&&el.tabIndex>=0);
        const index=fields.indexOf(document.activeElement);
        if(fields.length && (index<0 || event.shiftKey&&index===0 || !event.shiftKey&&index===fields.length-1)) {
          event.preventDefault();fields[event.shiftKey?fields.length-1:0].focus();
        }
        return;
      }
      const busy = $('#form-submit')?.disabled;
      if (busy && (['Escape','Enter'].includes(key)||key===' '&&target.matches('button'))) {event.preventDefault();toast('Saving. Please wait for the result.');return;}
      if (key==='Escape') {event.preventDefault();const row=target.closest('.purchase-line');if(row&&!row.querySelector('[data-purchase-results]').hidden){row.querySelector('[data-purchase-results]').hidden=true;row.querySelector('[data-purchase-search]').setAttribute('aria-expanded','false');return;}closeModal();return;}
      if(['PageDown','PageUp'].includes(key)&&dialog.querySelector('#invoice-results')){event.preventDefault();moveInvoicePage(key==='PageDown'?1:-1);return;}
      if (key==='F2'&&dialog.querySelector('.receipt-preview')) {event.preventDefault();closeModal('#product-search');openPOS();return;}
      if (key==='F10'&&dialog.querySelector('.receipt-preview')) {event.preventDefault();printInvoice(dialog.dataset.invoiceId);return;}
      if (key==='F3') {event.preventDefault();if(dialog.querySelector('#purchase-lines'))purchaseSearch(dialog);else{const field=dialog.querySelector('#invoice-search,#customer-query,#command-query,input[type=search],#f-barcode');field?.focus();field?.select();}return;}
      if (key==='F5') {event.preventDefault();return;}
      if (event.altKey&&!event.ctrlKey&&!event.metaKey) {
        const payment=dialog.querySelector('#f-payment'),methods={c:'Cash',u:'UPI',d:'Card',b:'Bank'};
        if(payment&&dialog.querySelector('.report-number')&&methods[lower]){event.preventDefault();payment.value=methods[lower];const paid=dialog.querySelector('#f-paid');paid?.focus();paid?.select();return;}
        if(lower==='p'&&dialog.querySelector('#f-paid')){event.preventDefault();dialog.querySelector('#f-paid').focus();dialog.querySelector('#f-paid').select();return;}
        if(lower==='a'&&dialog.querySelector('#purchase-lines')){event.preventDefault();const rows=[...dialog.querySelectorAll('.purchase-line')];const row=rows.find(r=>!r.querySelector('select').value)||addPurchaseLine();row?.querySelector('[data-purchase-search]').focus();return;}
        if(lower==='c'&&dialog.querySelector('#purchase-lines')){event.preventDefault();const row=target.closest('.purchase-line');const p=row&&product(row.querySelector('select').value);if(p){row.querySelector('[data-qty]').value=p.pack;purchaseTotal();row.querySelector('[data-qty]').focus();row.querySelector('[data-qty]').select();}return;}
      }
      if(key==='F8'&&dialog.querySelector('#purchase-lines')){event.preventDefault();dialog.querySelector('#f-paid')?.focus();dialog.querySelector('#f-paid')?.select();return;}
      if(target.matches('[data-purchase-search]')&&['ArrowDown','ArrowUp','Enter'].includes(key)&&!event.ctrlKey&&!event.metaKey&&!event.altKey&&!event.shiftKey){event.preventDefault();const row=target.closest('.purchase-line');if(key==='Enter')choosePurchase(row);else{if(row.querySelector('[data-purchase-results]').hidden)purchaseChoices(row);const size=row.purchaseChoices?.length||0;if(size)row.purchaseChoice=(row.purchaseChoice+(key==='ArrowDown'?1:-1)+size)%size;highlightPurchase(row);}return;}
      if(target.id==='customer-query'&&['ArrowDown','ArrowUp','Enter'].includes(key)){event.preventDefault();if(key==='Enter'){if(customerChoices.length)selectBillCustomer(customerChoices[customerChoice].id);}else if(customerChoices.length){customerChoice=(customerChoice+(key==='ArrowDown'?1:-1)+customerChoices.length)%customerChoices.length;$('#customer-choices').querySelectorAll('button').forEach((b,i)=>b.classList.toggle('selected',i===customerChoice));$('#customer-choices button.selected')?.scrollIntoView({block:'nearest'});}return;}
      if(key==='Enter'&&!event.ctrlKey&&!event.metaKey&&!event.altKey&&target.matches('form input:not([type=file]):not([type=hidden]),form select')){event.preventDefault();if(target.matches('[data-price]')&&!event.shiftKey&&target.reportValidity()&&target.closest('.purchase-line').querySelector('select').value){const row=target.closest('.purchase-line'),next=row.nextElementSibling||addPurchaseLine();next?.querySelector('[data-purchase-search]').focus();}else nextField(target,event.shiftKey);return;}
      if ((event.ctrlKey || event.metaKey) && key==='Enter') {
        const form = dialog.querySelector('form');if (form && !busy) {event.preventDefault();form.requestSubmit();}return;
      }
      if (target.id==='command-query' && ['ArrowDown','ArrowUp','Enter'].includes(key)) {
        event.preventDefault();
        if (key==='Enter') choose(selected);
        else if (palette.length) {selected=(selected+(key==='ArrowDown'?1:-1)+palette.length)%palette.length;highlight();}
      }
      return;
    }
    if ((event.ctrlKey || event.metaKey) && lower==='k') {event.preventDefault();commands();return;}
    if ((event.ctrlKey || event.metaKey) && key==='Enter' && page==='settings') {const form=$('#settings-form');if(form){event.preventDefault();form.requestSubmit();}return;}
    if (event.altKey && !event.shiftKey) {
      const route = routes.find(([shortcut])=>shortcut===lower);
      if (route) {event.preventDefault();go(route[1]);return;}
      if (lower==='k') {event.preventDefault();help();return;}
      if (lower==='m') {event.preventDefault();focusMain();return;}
      if (lower==='n') {event.preventDefault();$('.sidebar').classList.add('open');sidebar();$('#nav button')?.focus();return;}
      if (lower==='l') {event.preventDefault();($('#node-location') || $('#online-location'))?.focus();return;}
    }
    if(event.ctrlKey&&target.matches('[data-cart-quantity]')&&['ArrowUp','ArrowDown'].includes(key)){event.preventDefault();const rows=[...document.querySelectorAll('[data-cart-quantity]')],index=rows.indexOf(target),field=rows[Math.max(0,Math.min(rows.length-1,index+(key==='ArrowDown'?1:-1)))];field?.focus();field?.select();return;}
    if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey && key.startsWith('F')) return;
    const shortcuts = {F1:help,F2:openPOS,F3:focusSearch,F4:primaryAction,F5:()=>{if(page==='billing')billCustomerForm();},F6:()=>{if(page==='billing')focusQuantity();},F7:()=>{if(page==='billing'){$('#discount').focus();$('#discount').select();}},F8:()=>{if(page==='billing'&&canOperate('sale'))checkout();},F9:()=>{if(pageAllowed('billing'))invoiceList(page==='purchases'?'purchase':'sale');}};
    if (shortcuts[key]) {event.preventDefault();if(!event.repeat)shortcuts[key]();return;}
    if(key==='Enter'&&target.matches('[data-cart-quantity]')){event.preventDefault();if(target.reportValidity()&&changeQty(Number(target.closest('.cart-line').dataset.productId),target.value))$('#product-search').focus();return;}
    if(key==='Enter'&&target.id==='customer-mobile'){event.preventDefault();findCustomerMobile();return;}
    if(key==='Enter'&&target.id==='discount'){event.preventDefault();$('#product-search').focus();return;}
    if(['PageDown','PageUp'].includes(key)&&['billing','inventory','people'].includes(page)){event.preventDefault();const direction=key==='PageDown'?1:-1;if(page==='billing')moveProductPage(direction);if(page==='inventory')moveInventoryPage(direction);if(page==='people')movePeoplePage(direction);return;}
    if (key==='Escape' && $('.sidebar')?.classList.contains('open') && innerWidth<=850) {event.preventDefault();$('.sidebar').classList.remove('open');sidebar();$('#mobile-menu')?.focus();return;}
    if (target.id==='product-search' && key==='ArrowDown') {refreshProducts();const first=$('#product-results .product-card');if(first){event.preventDefault();first.focus();}return;}
    if (target.id==='product-search' && key==='Enter') {
      const exact=scanProduct(target.value);if(exact===null){event.preventDefault();event.stopImmediatePropagation();toast('Code matches multiple products. Correct the catalogue.',true);return;}if(!exact&&/^\d{6,}$/.test(target.value.trim())){event.preventDefault();event.stopImmediatePropagation();toast('Barcode not found. Add the barcode in Inventory.',true);return;}
      if (!exact) {refreshProducts();const cards=[...document.querySelectorAll('#product-results .product-card')];if(cards.length){event.preventDefault();event.stopImmediatePropagation();if(cards.length===1)cards[0].click();else cards[0].focus();}}return;
    }
    if(target.matches('#inventory-search,#people-search')&&['ArrowDown','Enter'].includes(key)){event.preventDefault();const host=page==='inventory'?$('#inventory-results'):$('#people-results');host?.querySelector('tbody button')?.focus();return;}
    if(target.matches('tbody button')&&['ArrowUp','ArrowDown','Home','End'].includes(key)){const row=target.closest('tr'),rows=[...row.parentElement.querySelectorAll('tr')],index=rows.indexOf(row),column=[...row.querySelectorAll('button')].indexOf(target),next=key==='Home'?0:key==='End'?rows.length-1:Math.max(0,Math.min(rows.length-1,index+(key==='ArrowDown'?1:-1)));event.preventDefault();const buttons=rows[next].querySelectorAll('button');(buttons[column]||buttons[0])?.focus();return;}
    if (target.matches('.product-card') && ['ArrowRight','ArrowLeft','ArrowUp','ArrowDown','Home','End'].includes(key)) {grid(event,target);return;}
    if (target.matches('.tabs button') && ['ArrowRight','ArrowLeft','Home','End'].includes(key)) {
      const buttons=[...target.parentElement.querySelectorAll('button')],index=buttons.indexOf(target);
      const next=key==='Home'?0:key==='End'?buttons.length-1:(index+(key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;
      event.preventDefault();buttons[next].focus();buttons[next].click();enhance();
    }
  },true);
  function install() {
    const baseRender=render;render=function(...args){const saved=remember();const result=baseRender(...args);enhance();if(!navigating&&!$('#modal').open)restore(saved,true);return result;};
    const baseNav=navTo;navTo=function(name){if(!pageAllowed(name))return baseNav(name);dialogVersion++;navigating=true;try{baseNav(name);enhance();focusMain();}finally{navigating=false;}};
    const baseOpen=openModal;openModal=function(...args){if(!$('#modal').open)opener=remember();const version=++dialogVersion;baseOpen(...args);enhance();requestAnimationFrame(()=>{const dialog=$('#modal');if(!dialog.open||version!==dialogVersion)return;const field=dialog.querySelector('form input:not([type=hidden]):not([type=checkbox]),form select,form textarea,#command-query,input[type=search],#invoice-search');(available(field)?field:dialog.querySelector('h2'))?.focus({preventScroll:true});});};
    const baseClose=closeModal;closeModal=function(destination){const saved=destination?remember($(destination)):$('#modal .receipt-preview')&&page==='billing'?remember($('#product-search')):opener;opener=null;const version=++dialogVersion;baseClose();queueMicrotask(()=>{if(version===dialogVersion&&!$('#modal').open&&!restore(saved))focusMain();});};
    $('#modal').addEventListener('cancel',event=>{event.preventDefault();if(!$('#form-submit')?.disabled)closeModal();});
    document.addEventListener('focusin',event=>{const row=event.target.closest('.cart-line');if(row)activeCartId=Number(row.dataset.productId);});
    document.addEventListener('click',event=>{if($('#form-submit')?.disabled&&event.target.closest('button[onclick="closeModal()"]')){event.preventDefault();event.stopImmediatePropagation();return;}if(event.target.closest('#mobile-menu,#nav-backdrop'))schedule();},true);
    new MutationObserver(schedule).observe(document.body,{subtree:true,childList:true});
    addEventListener('resize',sidebar);enhance();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();
